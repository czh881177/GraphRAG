"""
Dynamic sample data loader for The Story of The Stone (红楼梦)
Extracts first few chapters and chunks them for knowledge graph building
"""
import re


def extract_chapters(file_path, num_chapters=3, max_chars_per_chapter=5000):
    """
    Extract first N chapters from the text file

    Args:
        file_path: Path to orig.txt
        num_chapters: Number of chapters to extract
        max_chars_per_chapter: Maximum characters per chapter to avoid context overflow

    Returns:
        List of chapter texts
    """
    try:
        with open(file_path, 'r', encoding='gbk') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Try with gb18030 if gbk fails
        with open(file_path, 'r', encoding='gb18030') as f:
            content = f.read()

    # Split by chapter markers - looking for patterns like "第一回", "第二回" etc.
    # The text seems to use different formats, so we'll split by common patterns
    chapters = []

    # Try to find chapter boundaries
    # Pattern: 第X回 or 第X章
    chapter_pattern = r'第[一二三四五六七八九十百]+[回章]'
    matches = list(re.finditer(chapter_pattern, content))

    if len(matches) >= num_chapters + 1:
        for i in range(num_chapters):
            start = matches[i].start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            chapter_text = content[start:end].strip()

            # Truncate if too long
            if len(chapter_text) > max_chars_per_chapter:
                chapter_text = chapter_text[:max_chars_per_chapter]

            chapters.append(chapter_text)
    else:
        # Fallback: just take first N*max_chars_per_chapter characters
        chunk_size = max_chars_per_chapter
        for i in range(num_chapters):
            start = i * chunk_size
            end = start + chunk_size
            if start < len(content):
                chapters.append(content[start:end].strip())

    return chapters


def chunk_text(text, chunk_size=500, overlap=50):
    """
    Split text into overlapping chunks

    Args:
        text: Input text
        chunk_size: Size of each chunk in characters
        overlap: Overlap between chunks

    Returns:
        List of text chunks
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Try to break at sentence boundary
        if end < len(text):
            # Look for sentence endings: 。！？
            last_period = max(
                chunk.rfind('。'),
                chunk.rfind('！'),
                chunk.rfind('？'),
                chunk.rfind('.')
            )
            if last_period > chunk_size * 0.5:  # At least 50% through
                chunk = chunk[:last_period + 1]
                end = start + last_period + 1

        chunks.append(chunk.strip())
        start = end - overlap

        if start >= len(text):
            break

    return chunks


def get_sample_text():
    """
    Get sample text from The Story of The Stone
    Returns a single concatenated text with chapter markers
    """
    import os

    orig_path = os.path.join(os.path.dirname(__file__), '..', '..', 'origdata', 'orig.txt')

    if not os.path.exists(orig_path):
        raise FileNotFoundError(f"orig.txt not found at {orig_path}")

    # Extract first 3 chapters
    chapters = extract_chapters(orig_path, num_chapters=3, max_chars_per_chapter=3000)

    if not chapters:
        raise ValueError("Failed to extract chapters from orig.txt")

    # Concatenate chapters
    full_text = '\n\n'.join(chapters)

    return full_text


def get_chunks():
    """
    Get chunked text from The Story of The Stone
    Returns list of text chunks ready for knowledge graph building
    """
    full_text = get_sample_text()
    chunks = chunk_text(full_text, chunk_size=800, overlap=100)

    return chunks


if __name__ == '__main__':
    # Test the extraction
    print("Extracting chapters from The Story of The Stone...")

    try:
        chunks = get_chunks()
        print(f"\n✓ Extracted {len(chunks)} chunks")
        print(f"\nFirst chunk preview (first 200 chars):")
        print(chunks[0][:200] if chunks else "No chunks")

        print(f"\nChunk sizes:")
        for i, chunk in enumerate(chunks[:5]):
            print(f"  Chunk {i+1}: {len(chunk)} characters")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
