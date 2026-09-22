"""Build equivalent APA-style English and European Portuguese dissertations."""
from __future__ import annotations
import json
import shutil
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, KeepTogether
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.graphics.shapes import Drawing, Rect, String
from src.database import ROOT

AUTHOR = 'Nubia Aparecida Silva Almeida'
OUTPUT = ROOT / 'output/pdf'
CONTENT = ROOT / 'docs/dissertation'


def register_fonts():
    candidates = [Path('/System/Library/Fonts/Supplemental'), Path('/usr/share/fonts/truetype/liberation2'), Path('/usr/share/fonts/truetype/liberation')]
    for folder in candidates:
        regular = folder / ('Times New Roman.ttf' if folder.name == 'Supplemental' else 'LiberationSerif-Regular.ttf')
        if regular.exists():
            names = ['Times New Roman.ttf', 'Times New Roman Bold.ttf', 'Times New Roman Italic.ttf'] if folder.name == 'Supplemental' else ['LiberationSerif-Regular.ttf', 'LiberationSerif-Bold.ttf', 'LiberationSerif-Italic.ttf']
            for name, filename in zip(['ReportSerif', 'ReportSerif-Bold', 'ReportSerif-Italic'], names):
                pdfmetrics.registerFont(TTFont(name, str(folder / filename)))
            pdfmetrics.registerFontFamily('ReportSerif', normal='ReportSerif', bold='ReportSerif-Bold', italic='ReportSerif-Italic', boldItalic='ReportSerif-Bold')
            return
    raise RuntimeError('Install Times New Roman or Liberation Serif to build the reports')


def load_data():
    source = (ROOT / 'site/dashboard-data.js').read_text()
    prefix = 'window.LEGALTECH_DATA = '
    if not source.startswith(prefix):
        raise ValueError('Unexpected snapshot format')
    data = json.loads(source[len(prefix):].strip().removesuffix(';'))
    if data['metadata']['critical_findings'] != 0:
        raise ValueError('Report requires a snapshot with zero critical findings')
    return data


class ReportDoc(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, pagesize=LETTER, leftMargin=inch, rightMargin=inch,
                         topMargin=inch, bottomMargin=inch, **kwargs)
        self.addPageTemplates(PageTemplate(id='apa', frames=Frame(inch, inch, self.width, self.height,
                              leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0), onPage=self.page_number))

    def page_number(self, canvas, doc):
        canvas.setFont('ReportSerif', 12)
        canvas.drawRightString(LETTER[0] - inch, LETTER[1] - .5 * inch, str(doc.page))

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == 'Heading':
            label = flowable.getPlainText()
            key = f'heading-{self.seq.nextf("heading")}'
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(label, key, 0)
            self.notify('TOCEntry', (0, label, self.page, key))


def styles():
    body = ParagraphStyle('Body', fontName='ReportSerif', fontSize=12, leading=24, firstLineIndent=36, allowWidows=0, allowOrphans=0)
    return {
        'body': body,
        'plain': ParagraphStyle('Plain', parent=body, firstLineIndent=0),
        'center': ParagraphStyle('Center', parent=body, alignment=TA_CENTER, firstLineIndent=0),
        'title': ParagraphStyle('Title', parent=body, fontName='ReportSerif-Bold', alignment=TA_CENTER, firstLineIndent=0),
        'heading': ParagraphStyle('Heading', parent=body, fontName='ReportSerif-Bold', alignment=TA_CENTER, firstLineIndent=0, spaceAfter=12, keepWithNext=True),
        'label': ParagraphStyle('Label', parent=body, fontName='ReportSerif-Bold', firstLineIndent=0, leading=18, keepWithNext=True),
        'caption': ParagraphStyle('Caption', parent=body, fontName='ReportSerif-Italic', firstLineIndent=0, leading=18, keepWithNext=True),
        'small': ParagraphStyle('Small', parent=body, fontSize=10, leading=14, firstLineIndent=0),
        'reference': ParagraphStyle('Reference', parent=body, leftIndent=36, firstLineIndent=-36, splitLongWords=True),
        'code': ParagraphStyle('Code', fontName='Courier', fontSize=8, leading=15),
    }


def number(value, pt=False, decimals=0):
    result = f'{value:,.{decimals}f}'
    return result.replace(',', ' ').replace('.', ',') if pt else result


def metrics(data):
    m, inv, c = data['matters'], data['invoices'], data['consultations']
    return [len(m), sum(x['current_stage'] != 'closed' for x in m),
            sum(int(x['missing_document_count'] or 0) for x in m),
            sum(x['inquiry_count'] for x in data['inquiries']),
            sum(x['scheduled_count'] for x in c), sum(x['held_count'] for x in c),
            sum(x['accepted_count'] for x in c),
            *[sum(float(x[key] or 0) for x in inv) for key in ['invoiced_amount', 'paid_amount', 'outstanding_amount']],
            sum(x['calculated_status'] == 'overdue' for x in inv)]


def table(c, s, n, title, headers, rows):
    p = lambda text: Paragraph(escape(str(text)), s['small'])
    grid = [[p(h) for h in headers]] + [[p(v) for v in row] for row in rows]
    t = Table(grid, colWidths=[3.25*inch, 3.25*inch], repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([('LINEABOVE', (0,0), (-1,0), 1, colors.black),
                          ('LINEBELOW', (0,0), (-1,0), .7, colors.black),
                          ('LINEBELOW', (0,-1), (-1,-1), 1, colors.black),
                          ('VALIGN', (0,0), (-1,-1), 'TOP'),
                          ('TOPPADDING', (0,0), (-1,-1), 7),
                          ('BOTTOMPADDING', (0,0), (-1,-1), 7)]))
    return [KeepTogether([Paragraph(f"{c['table']} {n}", s['label']), Paragraph(escape(title), s['caption']), Spacer(1,8), t, Spacer(1,12)])]


def chart(labels, values, pt=False, currency=False):
    d = Drawing(468, 160)
    maximum = max(values) or 1
    for i, (label, value) in enumerate(zip(labels, values)):
        y = 125 - i * 42
        d.add(String(0, y+5, label, fontName='ReportSerif', fontSize=11))
        width = 195 * value / maximum
        d.add(Rect(146, y, width, 20, fillColor=colors.HexColor('#226b72'), strokeColor=None))
        display = ('EUR ' if currency else '') + number(value, pt, 2 if currency else 0)
        d.add(String(151 + width, y+5, display, fontName='ReportSerif', fontSize=9))
    return d


def references(pt):
    nd = 's.d.' if pt else 'n.d.'
    workflow_description = 'Documento de trabalho não publicado fornecido pela autora' if pt else 'Unpublished workflow document supplied by the project author'
    repository_description = 'Código-fonte e conjunto de dados sintéticos' if pt else 'Source code and synthetic dataset'
    return [
        f'Almeida, N. A. S. (2026). <i>Operacao LegalTech</i> [{repository_description}]. GitHub. https://github.com/asalmenubia/operacao_legaltech_2026_my_first_project',
        'American Psychological Association. (2020). <i>Publication manual of the American Psychological Association</i> (7th ed.).',
        f'GitHub. ({nd}). <i>What is GitHub Pages?</i> GitHub Docs. https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages',
        f'<i>Law office intake and matter workflow</i>. ({nd}). [{workflow_description}; law_firm_workflow_document.pdf].',
        f'Meta. ({nd}). <i>WhatsApp Cloud API</i>. Postman API Network. https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api',
        f'PostgreSQL Global Development Group. ({nd}). <i>PostgreSQL documentation: Constraints</i>. https://www.postgresql.org/docs/current/ddl-constraints.html',
        f'Python Software Foundation. ({nd}-a). <i>imaplib: IMAP4 protocol client</i>. https://docs.python.org/3/library/imaplib.html',
        f'Python Software Foundation. ({nd}-b). <i>smtplib: SMTP protocol client</i>. https://docs.python.org/3/library/smtplib.html',
        f'WhatsApp. ({nd}-a). <i>Webhooks: Start</i>. WhatsApp Business Platform Node.js SDK. https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/webhooks/start/',
        f'WhatsApp. ({nd}-b). <i>WhatsApp business messaging policy</i>. https://business.whatsapp.com/policy',
    ]


def build_report(language, data):
    c = json.loads((CONTENT / f'{language}.json').read_text())
    pt = language == 'pt-PT'
    s = styles()
    p = lambda value, kind='body': Paragraph(escape(value), s[kind])
    target = OUTPUT / f'operacao_legaltech_dissertation_{language}.pdf'
    doc = ReportDoc(str(target), title=c['title'], author=AUTHOR,
                    subject='Dissertação de projeto' if pt else 'Project dissertation', lang=language)
    story = [Spacer(1,inch), p(c['title'],'title'), Spacer(1,36), p(AUTHOR,'center'),
             p(c['institution'],'center'), p(c['course'],'center'), p(c['project'],'center'),
             Spacer(1,24), p(c['date'],'center'), Spacer(1,36),
             p('Apresentação adaptada à APA, 7.ª edição (American Psychological Association, 2020).' if pt else 'Presentation adapted to APA, 7th edition (American Psychological Association, 2020).','center'),
             PageBreak(), p(c['ack_title'],'heading'), p(c['ack']),
             PageBreak(), p(c['abstract_title'],'heading'), p(c['abstract'],'plain'), Spacer(1,12), p(c['keywords'],'plain'),
             PageBreak(), p(c['contents'],'title'), Spacer(1,12)]
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle('TOC', fontName='ReportSerif', fontSize=12, leading=22)]
    story.append(toc)
    values = metrics(data)
    for index, section in enumerate(c['sections']):
        story.extend([PageBreak(), p(section['title'],'heading')])
        story.extend(p(paragraph) for paragraph in section['paragraphs'])
        if index == 2:
            story.extend([Spacer(1,12)] + table(c,s,1,c['tables']['mapping_title'],c['tables']['mapping_headers'],c['tables']['mapping_rows']))
        if index == 3:
            story.extend([Spacer(1,12)] + table(c,s,2,c['tables']['schedule_title'],c['tables']['schedule_headers'],c['tables']['schedule_rows']))
        if index == 5:
            rows = [[label, ('EUR ' if 7 <= i <= 9 else '') + number(v,pt,2 if 7 <= i <= 9 else 0)]
                    for i,(label,v) in enumerate(zip(c['tables']['results_labels'],values))]
            story.extend([PageBreak()] + table(c,s,3,c['tables']['results_title'],c['tables']['results_headers'],rows))
            stamp = data['metadata']['generated_at']
            story.append(p(('Data do conjunto analítico: ' if pt else 'Analytical snapshot timestamp: ') + stamp, 'small'))
            figure_values = [[values[0]-values[1],values[1]], [values[2],sum(int(x['missing_document_count'] or 0)>0 for x in data['matters'])], values[4:7],values[7:10]]
            for f, vals in enumerate(figure_values):
                if f % 2 == 0:
                    story.append(PageBreak())
                story.append(KeepTogether([p(f"{c['figure']} {f+1}",'label'),p(c['figures'][f],'caption'),Spacer(1,12),
                                          chart(c['figure_labels'][f], vals,pt,f==3),p(c['figure_note'],'small'),Spacer(1,24)]))
    story.extend([PageBreak(),p(c['references_title'],'heading')])
    story.extend(Paragraph(ref,s['reference']) for ref in references(pt))
    story.extend([PageBreak(),p(c['appendix_title'],'heading'),p(c['appendix']),Spacer(1,12)])
    commands = ['uv sync','uv run python -m alembic upgrade head','uv run python -m unittest discover -s tests -v',
                'uv run python -m tests.integration_communications','uv run python -m src.build_dissertation_report',
                'uv run python -m src.communications queue']
    story.extend(p(command,'code') for command in commands)
    doc.multiBuild(story)
    for folder in [ROOT/'site/reports', ROOT]:
        folder.mkdir(parents=True,exist_ok=True)
        shutil.copy2(target, folder/target.name)
    return target


def main():
    register_fonts()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    data = load_data()
    for language in ['en','pt-PT']:
        target = build_report(language,data)
        print(f'Report written: {target}')
    # Preserve existing download links: the original filename is the English edition.
    for folder in [OUTPUT,ROOT,ROOT/'site/reports']:
        shutil.copy2(OUTPUT/'operacao_legaltech_dissertation_en.pdf',folder/'operacao_legaltech_dissertation_report.pdf')


if __name__ == '__main__':
    main()
