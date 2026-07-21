from github.api import get_pr_files, get_file_content
from logs.logger import get_logger

logger = get_logger("file_context")

# Ek file ka poora content tabhi bhejo jab wo itna bada na ho ki context
# bloat ho jaaye — warna sirf diff pe fallback karo.
MAX_FULL_FILE_CHARS = 8000

# Poore context ka hard cap — Gemini ka context window bada hai,
# lekin cost aur latency dono ke liye limit rakhna zaroori hai.
MAX_TOTAL_CONTEXT_CHARS = 24000

# Bahut badi PR (20+ files) mein har file ka poora content nahi fetch karenge —
# sirf pehli N files, baaki sirf diff se cover ho jaayengi.
MAX_FILES_WITH_FULL_CONTENT = 5


async def build_file_context(repo: str, pr_number: int, head_ref: str, diff: str) -> str:
    """
    Sirf diff dena kaafi nahi — agar bug diff ke bahar hai (jaise ek existing
    helper function jisko PR touch nahi kar raha, lekin uske behaviour pe
    depend kar raha hai), toh agent usko diff mein kabhi nahi dekh payega.

    Ye function changed files ka poora content bhi fetch karta hai (size allow
    karne tak) aur diff ke saath combine karke ek richer context string banata hai.
    """
    files = await get_pr_files(repo, pr_number)
    if not files:
        # PR files list nahi mil paayi — purana diff-only behavior pe fallback
        logger.warning(f"No file list for PR #{pr_number} — falling back to diff-only context")
        return f"CODE DIFF:\n{diff[:4000]}"

    sections = [f"CODE DIFF ({len(files)} file(s) changed):\n{diff[:6000]}"]
    total_chars = len(sections[0])

    files_with_content = 0
    for f in files:
        if files_with_content >= MAX_FILES_WITH_FULL_CONTENT:
            break
        if total_chars >= MAX_TOTAL_CONTEXT_CHARS:
            break

        filename = f.get("filename", "")
        status = f.get("status", "")
        if not filename or status == "removed":
            continue

        content = await get_file_content(repo, filename, head_ref)
        if not content:
            continue

        if len(content) > MAX_FULL_FILE_CHARS:
            logger.info(f"Skipping full content for {filename} — too large ({len(content)} chars)")
            continue

        section = f"\n\n--- FULL FILE (for context — not all of this changed): {filename} ---\n{content}"
        if total_chars + len(section) > MAX_TOTAL_CONTEXT_CHARS:
            break

        sections.append(section)
        total_chars += len(section)
        files_with_content += 1

    logger.info(
        f"Built file context for PR #{pr_number}: {files_with_content} full file(s), "
        f"{total_chars} total chars"
    )
    return "".join(sections)
