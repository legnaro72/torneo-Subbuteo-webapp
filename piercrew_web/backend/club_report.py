"""Printable Gazzetta-style club composition and archive report."""
from collections import Counter
from datetime import datetime
from pathlib import Path

from fpdf import FPDF


NAVY = (26, 54, 93)
GOLD = (212, 175, 55)
PALE = (230, 235, 245)


def printable(value, limit=None):
    result = str(value or '').encode('latin-1', 'replace').decode('latin-1')
    return result if limit is None or len(result) <= limit else result[:limit - 3] + '...'


class ClubPDF(FPDF):
    def __init__(self):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.set_margins(10, 40, 10)
        self.set_auto_page_break(True, 12)
        self.logo = Path(__file__).resolve().parents[1] / 'public' / 'logo-piercrew.jpg'

    def header(self):
        self.set_fill_color(*NAVY)
        self.rect(0, 0, 210, 33, 'F')
        self.set_fill_color(*GOLD)
        self.rect(0, 33, 210, 1.4, 'F')
        if self.logo.is_file():
            self.image(str(self.logo), x=12, y=5, w=22, h=22)
        self.set_xy(40, 6)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 20)
        self.cell(160, 11, 'IL GAZZETTINO DELLA PIERCREW', new_x='LMARGIN', new_y='NEXT')
        self.set_x(40)
        self.set_font('Helvetica', 'I', 10)
        self.cell(160, 7, 'Composizione Club PierCrew | Aggiornato il ' + datetime.now().strftime('%d/%m/%Y alle %H:%M'))
        self.set_y(41)

    def footer(self):
        self.set_fill_color(*NAVY)
        self.rect(0, 287, 210, 10, 'F')
        self.set_y(-8)
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(255, 255, 255)
        self.cell(0, 6, f'Pagina {self.page_no()} - La Gazzetta della PierCrew', align='C')

    def room(self, height):
        if self.get_y() + height > 282:
            self.add_page()

    def section_title(self, value):
        self.room(15)
        self.set_fill_color(*PALE)
        self.set_text_color(*NAVY)
        self.set_font('Helvetica', 'B', 16)
        self.cell(190, 11, printable(value), border=1, fill=True, align='C', new_x='LMARGIN', new_y='NEXT')
        self.ln(4)


def draw_roster(pdf, players):
    pdf.section_title('ROSA GIOCATORI')
    average = sum(p['potential'] for p in players) / len(players) if players else 0
    pdf.set_font('Helvetica', 'I', 10)
    pdf.set_text_color(95, 95, 95)
    pdf.cell(190, 7, f'Totale tesserati: {len(players)} | Potenziale medio: {average:.1f}/10', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(3)
    widths = [10, 75, 87, 18]
    for index, p in enumerate(sorted(players, key=lambda p: (-p['potential'], p['name'].casefold()))):
        pdf.room(17 if index == 0 else 8)
        if index == 0 or pdf.get_y() < 50:
            pdf.set_fill_color(*NAVY)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Helvetica', 'B', 9)
            for width, value in zip(widths, ['#', 'Giocatore', 'Squadra', 'Pot.']):
                pdf.cell(width, 7, value, border=1, align='C', fill=True)
            pdf.ln()
        pdf.set_fill_color(*(245, 248, 250) if index % 2 == 0 else (255, 255, 255))
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Helvetica', '', 9)
        for width, value in zip(widths, [str(index + 1), printable(p['name'], 32), printable(p['team'], 38), str(p['potential'])]):
            pdf.cell(width, 7, ' ' + value, border=1, fill=True, align='C' if width in (10, 18) else 'L')
        pdf.ln()
    if not players:
        pdf.set_text_color(90, 90, 90)
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(190, 9, 'Nessun giocatore registrato.', align='C', new_x='LMARGIN', new_y='NEXT')


def draw_potential(pdf, players):
    pdf.add_page()
    pdf.section_title('DISTRIBUZIONE POTENZIALE')
    counts = Counter(p['potential'] for p in players)
    for level in sorted(counts, reverse=True):
        pdf.room(9)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(25, 8, f'{level}/10')
        pdf.set_fill_color(*(GOLD if level >= 8 else (42, 157, 143) if level >= 6 else (150, 160, 175) if level >= 4 else (200, 80, 80)))
        pdf.cell(min(counts[level] * 12, 130), 8, '', fill=True)
        pdf.cell(35, 8, f'  {counts[level]} giocatori', new_x='LMARGIN', new_y='NEXT')
        pdf.ln(3)


def draw_palmares(pdf, players):
    pdf.add_page()
    pdf.section_title('PALMARES GIOCATORI')
    categories = [('CAMPIONATI VINTI', 'NCampionatiVinti', 'listaCampionatiVinti', GOLD),
                  ('FASI FINALI A GIRONI VINTE', 'NGironiFFVinti', 'listaGironiFFVinti', (42, 157, 143)),
                  ('ELIMINAZIONE DIRETTA VINTE', 'NFFElimDirettaVinte', 'listaFFElimDirettaVinte', (200, 80, 80))]
    for title, count, names, color in categories:
        winners = sorted((p for p in players if p[count] > 0), key=lambda p: (-p[count], p['name'].casefold()))
        if not winners:
            continue
        pdf.room(25)
        pdf.set_fill_color(*color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(190, 9, '  ' + title, border=1, fill=True, new_x='LMARGIN', new_y='NEXT')
        for player in winners:
            pdf.room(8)
            pdf.set_fill_color(245, 248, 250)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Helvetica', 'B', 9)
            pdf.cell(50, 8, ' ' + printable(player['name'], 27), border=1, fill=True)
            pdf.cell(15, 8, str(player[count]), border=1, align='C', fill=True)
            pdf.set_font('Helvetica', '', 8)
            pdf.cell(125, 8, ' ' + printable(', '.join(player[names]), 74), border=1, fill=True, new_x='LMARGIN', new_y='NEXT')
        pdf.ln(5)
    if not any(p[count] for _, count, _, _ in categories for p in players):
        pdf.set_text_color(90, 90, 90)
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(190, 9, 'Nessun trofeo registrato.', align='C', new_x='LMARGIN', new_y='NEXT')


def draw_archive(pdf, players, italian, swiss):
    pdf.add_page()
    pdf.section_title('ARCHIVIO TORNEI')
    for heading, names in (("TORNEI ALL'ITALIANA", italian), ('TORNEI SVIZZERI', swiss)):
        pdf.room(22)
        pdf.set_fill_color(*NAVY)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(190, 9, f'  {heading} ({len(names)})', fill=True, new_x='LMARGIN', new_y='NEXT')
        if not names:
            pdf.set_text_color(90, 90, 90)
            pdf.set_font('Helvetica', 'I', 9)
            pdf.cell(190, 8, 'Nessun torneo registrato.', new_x='LMARGIN', new_y='NEXT')
        for index, name in enumerate(names):
            pdf.room(8)
            pdf.set_fill_color(*(245, 248, 250) if index % 2 == 0 else (255, 255, 255))
            pdf.set_text_color(*(GOLD if 'campionato' in name.casefold() else (0, 0, 0)))
            pdf.set_font('Helvetica', 'B' if 'campionato' in name.casefold() else '', 9)
            pdf.cell(12, 7, str(index + 1), border=1, align='C', fill=True)
            pdf.cell(178, 7, '  ' + printable(name, 85), border=1, fill=True, new_x='LMARGIN', new_y='NEXT')
        pdf.ln(8)
    pdf.room(50)
    pdf.set_fill_color(*GOLD)
    pdf.set_text_color(*NAVY)
    pdf.set_font('Helvetica', 'B', 13)
    pdf.cell(190, 10, 'RIEPILOGO CLUB', border=1, fill=True, align='C', new_x='LMARGIN', new_y='NEXT')
    average = sum(p['potential'] for p in players) / len(players) if players else 0
    for label, value in [('Giocatori tesserati', str(len(players))), ('Potenziale medio', f'{average:.1f}/10'),
                         ("Tornei all'italiana", str(len(italian))), ('Tornei svizzeri', str(len(swiss))),
                         ('Totale tornei', str(len(italian) + len(swiss)))]:
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(130, 7, '  ' + label, border=1)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(60, 7, value, border=1, align='R', new_x='LMARGIN', new_y='NEXT')


def render_club_pdf(players, italian, swiss):
    pdf = ClubPDF()
    pdf.add_page()
    draw_roster(pdf, players)
    draw_potential(pdf, players)
    draw_palmares(pdf, players)
    draw_archive(pdf, players, italian, swiss)
    return bytes(pdf.output())
