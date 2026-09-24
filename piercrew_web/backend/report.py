"""The Italian tournament's Gazzettino-style PDF, adapted from the classic app."""
from datetime import datetime
from pathlib import Path

from fpdf import FPDF


NAVY = (26, 54, 93)
GOLD = (212, 175, 55)
PALE = (230, 235, 245)


def printable(value):
    return str(value).encode('latin-1', 'replace').decode('latin-1')


class GazzettaPDF(FPDF):
    def __init__(self, tournament_name):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.tournament_name = tournament_name
        self.logo = Path(__file__).resolve().parents[1] / 'public' / 'logo-piercrew.jpg'
        self.set_margins(10, 40, 10)
        self.set_auto_page_break(True, 10)

    def header(self):
        self.set_fill_color(*NAVY)
        self.rect(0, 0, 210, 33, 'F')
        self.set_fill_color(*GOLD)
        self.rect(0, 33, 210, 1.4, 'F')
        if self.logo.is_file():
            self.image(str(self.logo), x=12, y=5, w=22, h=22)
        self.set_xy(40, 6)
        self.set_font('Helvetica', 'B', 20)
        self.set_text_color(255, 255, 255)
        self.cell(160, 11, 'IL GAZZETTINO DELLA PIERCREW', new_x='LMARGIN', new_y='NEXT')
        self.set_x(40)
        self.set_font('Helvetica', 'I', 10)
        self.set_text_color(220, 225, 235)
        date = datetime.now().strftime('%d/%m/%Y alle %H:%M')
        subtitle = f'Referto ufficiale: {self.tournament_name} | Aggiornato il {date}'
        self.cell(160, 7, self._short(subtitle, 91), new_x='LMARGIN', new_y='NEXT')
        self.set_y(41)

    def footer(self):
        self.set_fill_color(*NAVY)
        self.rect(0, 287, 210, 10, 'F')
        self.set_y(-8)
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(255, 255, 255)
        self.cell(0, 6, f'Pagina {self.page_no()} - Gestionale Tornei Subbuteo', align='C')

    @staticmethod
    def _short(value, limit):
        value = printable(value)
        return value if len(value) <= limit else value[:limit-3] + '...'

    def ensure_space(self, height):
        if self.get_y() + height > 282:
            self.add_page()


def render_tournament_pdf(data):
    pdf = GazzettaPDF(data['name'])
    pdf.add_page()
    groups = list(dict.fromkeys(row['group'] for row in data['matches']))
    complete = data['matches'] and all(row['valid'] for row in data['matches'])

    if complete and data['standings']:
        winners = [next((row['Squadra'] for row in data['standings'] if row['Girone'] == group), None) for group in groups]
        winners = [f'{group}: {winner}' if len(groups) > 1 else winner for group, winner in zip(groups, winners) if winner]
        if winners:
            pdf.set_fill_color(255, 215, 0)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Helvetica', 'B', 12)
            pdf.multi_cell(190, 10, printable('CAMPIONI DEL TORNEO: ' + ' - '.join(winners)), border=1, fill=True, align='C', new_x='LMARGIN', new_y='NEXT')
            pdf.ln(6)

    for group in groups:
        standings = [row for row in data['standings'] if row['Girone'] == group]
        pdf.ensure_space(32 + len(standings) * 7)
        pdf.set_fill_color(*PALE)
        pdf.set_text_color(*NAVY)
        pdf.set_font('Helvetica', 'B', 16)
        title = f'CLASSIFICA: {group.upper()}' if len(groups) > 1 else 'CLASSIFICA GENERALE'
        pdf.cell(190, 10, printable(title), border=1, fill=True, align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.ln(3)
        widths = [10, 98, 12, 10, 10, 10, 10, 12, 12, 16]
        headers = ['Pos', 'Squadra', 'PTI', 'G', 'V', 'P', 'S', 'GF', 'GS', 'DR']
        pdf.set_fill_color(*NAVY)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 10)
        for width, header in zip(widths, headers):
            pdf.cell(width, 8, header, border=1, align='C', fill=True)
        pdf.ln()
        if not standings:
            pdf.set_text_color(70, 70, 70)
            pdf.set_font('Helvetica', 'I', 10)
            pdf.cell(190, 8, 'Nessuna partita validata', border=1, align='C', new_x='LMARGIN', new_y='NEXT')
        for index, row in enumerate(standings):
            pdf.set_fill_color(*(245, 248, 250) if index % 2 == 0 else (255, 255, 255))
            pdf.set_text_color(0, 0, 0)
            values = [str(index+1), pdf._short(row['Squadra'], 30), str(row['Punti']), str(row['G']), str(row['V']), str(row['P']), str(row['S']), str(row['GF']), str(row['GS']), str(row['DR'])]
            for col, (width, value) in enumerate(zip(widths, values)):
                pdf.set_font('Helvetica', 'B' if col == 1 else '', 10)
                pdf.cell(width, 7, printable(value), border=1, align='L' if col == 1 else 'C', fill=True)
            pdf.ln()
        pdf.ln(8)

        group_rows = [row for row in data['matches'] if row['group'] == group]
        days = sorted({row['day'] for row in group_rows})
        for day in days:
            matches = [row for row in group_rows if row['day'] == day]
            pdf.ensure_space(18 + 7 * len(matches))
            pdf.set_fill_color(*PALE)
            pdf.set_text_color(*NAVY)
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(190, 8, printable(f'Giornata {day}' + (f' - {group}' if len(groups) > 1 else '')), fill=True, new_x='LMARGIN', new_y='NEXT')
            widths = [60, 30, 60, 40]
            pdf.set_fill_color(240, 240, 240)
            pdf.set_text_color(90, 90, 90)
            pdf.set_font('Helvetica', 'B', 9)
            for width, header in zip(widths, ['Casa', 'Risultato', 'Ospite', 'Status']):
                pdf.cell(width, 6, header, border=1, align='C', fill=True)
            pdf.ln()
            for index, row in enumerate(matches):
                pdf.set_fill_color(*(248, 249, 250) if index % 2 == 0 else (255, 255, 255))
                pdf.set_text_color(0, 0, 0)
                pdf.set_font('Helvetica', '' if row['valid'] else 'I', 10)
                pdf.cell(widths[0], 7, '  ' + pdf._short(row['home'], 28), border=1, fill=True)
                pdf.set_font('Helvetica', 'B', 11)
                score = f"{row['home_goals']} - {row['away_goals']}" if row['valid'] else ' - '
                pdf.cell(widths[1], 7, score, border=1, align='C', fill=True)
                pdf.set_font('Helvetica', '' if row['valid'] else 'I', 10)
                pdf.cell(widths[2], 7, '  ' + pdf._short(row['away'], 28), border=1, fill=True)
                pdf.set_text_color(*(42, 157, 143) if row['valid'] else (160, 160, 160))
                pdf.set_font('Helvetica', 'B', 8)
                pdf.cell(widths[3], 7, 'UFFICIALE' if row['valid'] else 'DA GIOCARE', border=1, align='C', fill=True)
                pdf.ln()
            pdf.ln(4)
        if group != groups[-1]:
            pdf.ln(6)
    return bytes(pdf.output())


def render_knockout_pdf(data):
    pdf = GazzettaPDF(data['name'])
    pdf.add_page()
    if data.get('winner'):
        pdf.set_fill_color(255, 215, 0)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Helvetica', 'B', 13)
        pdf.multi_cell(190, 12, printable('CAMPIONE: ' + data['winner']), border=1, fill=True, align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.ln(8)
    rounds = sorted({row['round'] for row in data['matches']})
    for round_number in rounds:
        matches = [row for row in data['matches'] if row['round'] == round_number]
        pdf.ensure_space(18 + len(matches) * 13)
        pdf.set_fill_color(*PALE)
        pdf.set_text_color(*NAVY)
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(190, 10, printable(matches[0]['round_name'].upper()), border=1, fill=True, align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.ln(4)
        for index, match in enumerate(matches, 1):
            pdf.ensure_space(14)
            pdf.set_fill_color(*(248, 249, 250) if index % 2 else (255, 255, 255))
            pdf.set_text_color(20, 30, 40)
            pdf.set_font('Helvetica', '', 10)
            pdf.cell(15, 11, str(index), border=1, align='C', fill=True)
            pdf.cell(64, 11, '  ' + pdf._short(match['home'], 31), border=1, fill=True)
            pdf.set_font('Helvetica', 'B', 11)
            score = f"{match['home_goals']} - {match['away_goals']}" if match['valid'] else ' - '
            pdf.cell(30, 11, score, border=1, align='C', fill=True)
            pdf.set_font('Helvetica', '', 10)
            pdf.cell(64, 11, '  ' + pdf._short(match['away'], 31), border=1, fill=True)
            pdf.set_font('Helvetica', 'B', 8)
            pdf.cell(17, 11, 'OK' if match['valid'] else 'ATTESA', border=1, align='C', fill=True)
            pdf.ln()
        pdf.ln(8)
    return bytes(pdf.output())
