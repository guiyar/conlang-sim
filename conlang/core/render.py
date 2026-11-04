"""Aligned text, segmentation, and interlinear gloss rendering."""

def render(words, gloss=False):
    text = " ".join(word.surface() for word in words)
    segmented = " ".join(word.segmented() for word in words)
    if not gloss:
        return text
    gloss_line = " ".join(word.gloss() for word in words)
    return f"{text}\n{segmented}\n{gloss_line}"