"""Evidence-linked extractive drafts and standard-library Word export."""
import io
import re
import zipfile
from xml.sax.saxutils import escape


def timestamp(seconds):
    value = max(0, int(seconds))
    return f'{value // 3600:02d}:{value // 60 % 60:02d}:{value % 60:02d}'


def draft_minutes(segments, title):
    groups = {'讨论摘录': [], '决定候选（请核对）': [], '待办候选（请核对）': []}
    for segment in segments:
        text = segment['text'].strip()
        if not text:
            continue
        item = f"[{timestamp(segment['start'])}] {text}"
        if re.search(r'决定|确定|同意|通过|批准|\b(decided|agreed|approved|decision)\b', text, re.I):
            groups['决定候选（请核对）'].append(item)
        if re.search(r'负责|待办|跟进|完成|截止|提交|\b(action|follow.up|deadline|will|assigned)\b', text, re.I):
            groups['待办候选（请核对）'].append(item)
        groups['讨论摘录'].append(item)
    # Representative excerpts across the recording, never invent participants or deadlines.
    excerpts = groups['讨论摘录']
    if len(excerpts) > 18:
        groups['讨论摘录'] = [excerpts[round(i * (len(excerpts) - 1) / 17)] for i in range(18)]
    lines = [title or '会议记录', '', '本地摘录草稿 · 按关键词归类，不是完整语义总结。请回听核对。',
             '会议日期：未明确', '参会人员：未明确（第一版不自动区分发言人）', '']
    for heading, items in groups.items():
        lines += [heading] + (items or ['未提取到；不代表会议中没有该内容。']) + ['']
    lines += ['待确认', '请核对人名、数字、否定语气、负责人和截止日期；不要把候选内容直接视为决定。']
    return '\n'.join(lines)


def make_docx(title, text):
    def paragraph(value, bold=False):
        props = '<w:rPr><w:b/></w:rPr>' if bold else ''
        return '<w:p><w:r>' + props + '<w:t xml:space="preserve">' + escape(value) + '</w:t></w:r></w:p>'
    # XML 1.0 disallows most control characters.
    title = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', title)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    document = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
    document += paragraph(title, True) + ''.join(paragraph(line) for line in text.splitlines())
    document += '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>'
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr('_rels/.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        archive.writestr('word/document.xml', document)
    return output.getvalue()
