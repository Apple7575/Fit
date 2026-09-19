import unittest

from pipeline.business_report.doc import Document
from pipeline.business_report.form_tables import form_tables, header_paths, parse_number, period_year, split_header


def _doc(body: str) -> Document:
    return Document.from_bytes(f"<DOCUMENT>{body}</DOCUMENT>".encode(), rcept_no="20260319000001")


class NumberTest(unittest.TestCase):
    def test_parse_number_forms(self):
        self.assertEqual(parse_number("22,133"), 22133.0)
        self.assertEqual(parse_number("(1,109)"), -1109.0)
        self.assertEqual(parse_number("△7,685"), -7685.0)
        self.assertEqual(parse_number("4.91%"), 4.91)
        self.assertEqual(parse_number("- 897"), -897.0)
        self.assertIsNone(parse_number("-"))
        self.assertIsNone(parse_number("적자전환"))
        self.assertIsNone(parse_number("47,299원/명"), "단위가 붙은 값은 숫자로 보지 않는다")

    def test_period_year(self):
        self.assertEqual(period_year("2023년(제39기)", 2025, 39), 2023)
        self.assertEqual(period_year("제51기", 2024, 51), 2024)
        self.assertEqual(period_year("제49기", 2024, 51), 2022)
        self.assertIsNone(period_year("합계", 2024, 51))


class HeaderTest(unittest.TestCase):
    def test_unit_line_is_not_header_and_two_header_rows_merge(self):
        doc = _doc("""<TITLE>4. 매출 및 수주상황</TITLE>
          <TABLE><TBODY>
            <TR><TD>(단위 : 백만원)</TD></TR>
            <TR><TD>품목</TD><TD>수주일자</TD><TD>납기</TD><TD>수주총액</TD><TD>수주총액</TD><TD>수주잔고</TD><TD>수주잔고</TD></TR>
            <TR><TD>품목</TD><TD>수주일자</TD><TD>납기</TD><TD>수량</TD><TD>금액</TD><TD>수량</TD><TD>금액</TD></TR>
            <TR><TD>철도A</TD><TD>2016.01.21</TD><TD>2031.06.30</TD><TD>-</TD><TD>365,656</TD><TD>-</TD><TD>212,179</TD></TR>
          </TBODY></TABLE>""")
        header, body, unit = split_header(doc.tables[0])
        self.assertEqual(unit, "백만원")
        self.assertEqual(len(header), 2)
        self.assertEqual(len(body), 1)
        self.assertEqual(header_paths(header), ("품목", "수주일자", "납기", "수주총액>수량", "수주총액>금액", "수주잔고>수량", "수주잔고>금액"))


class TuCellTest(unittest.TestCase):
    def test_tu_cells_are_kept_in_matrix(self):
        # 덕산테코피아 타법인출자 실측: 상장여부·최초취득일자가 <TU> 셀이라 예전 설정(TD·TE·TH)에서는 빠져 열이 밀렸다
        doc = _doc("""<TITLE>3. 타법인출자 현황(상세)</TITLE>
          <TABLE><THEAD><TR><TH>법인명</TH><TH>상장여부</TH><TH>최초취득일자</TH><TH>출자목적</TH><TH>최초취득금액</TH><TH>기말잔액</TH></TR></THEAD>
          <TBODY><TR><TE>BNA(CAM)Corp.</TE><TU AUNIT="INV_YN">비상장</TU><TU AUNIT="INV_GET">2008년 05월 16일</TU><TE>사업 다각화</TE><TE>1,219</TE><TE>400</TE></TR></TBODY></TABLE>""")
        self.assertEqual(doc.tables[0].m[1], ["BNA(CAM)Corp.", "비상장", "2008년 05월 16일", "사업 다각화", "1,219", "400"])
        forms = form_tables(doc, report_year=2025)
        self.assertEqual(forms[0].status, "OK")
        row = {r.column_key: r for r in forms[0].rows}
        self.assertEqual(row["최초취득금액"].value_num, 1219.0)


class FormTablesTest(unittest.TestCase):
    def test_employee_status_rows(self):
        doc = _doc("""<TITLE>1. 임원 및 직원 등의 현황</TITLE>
          <TABLE><THEAD><TR><TD>구 분</TD><TD>인원수</TD><TD>연간급여 총액</TD><TD>1인평균 급여액</TD><TD>비고</TD></TR></THEAD>
          <TBODY>
            <TR><TD>미등기임원</TD><TD>2</TD><TD>153,127,300</TD><TD>77,563,650</TD><TD>-</TD></TR>
            <TR><TD>직원</TD><TD>328</TD><TD>21,000,000,000</TD><TD>64,024,390</TD><TD>-</TD></TR>
          </TBODY></TABLE>""")
        forms = form_tables(doc, report_year=2025)
        self.assertEqual([f.form_code for f in forms], ["EXECUTIVE_PAY"])
        form = forms[0]
        self.assertEqual(form.status, "OK")
        self.assertEqual(form.unit, "백만원", "단위 메타가 없으면 서식 기본 단위")
        by = {(r.row_labels, r.column_key): r for r in form.rows}
        self.assertEqual(by[(("직원",), "인원수")].value_num, 328.0)
        self.assertEqual(by[(("직원",), "1인평균급여액")].value_num, 64024390.0)
        self.assertEqual(by[(("직원",), "1인평균급여액")].parse_status, "NUMBER")

    def test_order_backlog_uses_period_years_and_labels(self):
        doc = _doc("""<TITLE>4. 매출 및 수주상황</TITLE>
          <P>가. 매출실적 (단위: 백만원)</P>
          <TABLE><TBODY>
            <TR><TD>사업부문</TD><TD>매출유형</TD><TD>품 목</TD><TD>품 목</TD><TD>제51기</TD><TD>제50기</TD></TR>
            <TR><TD>전기변환 기기류부문</TD><TD>제품매출</TD><TD>수배전반류</TD><TD>수 출</TD><TD>113</TD><TD>1,076</TD></TR>
            <TR><TD>전기변환 기기류부문</TD><TD>제품매출</TD><TD>수배전반류</TD><TD>내 수</TD><TD>40,087</TD><TD>43,519</TD></TR>
          </TBODY></TABLE>""")
        forms = form_tables(doc, report_year=2024)
        self.assertEqual(forms[0].form_code, "SALES_BY_PRODUCT")
        rows = {(r.row_labels[-1], r.column_key): r for r in forms[0].rows}
        row = rows[("수출", "제51기")]  # 행렬 단계에서 셀 안 공백이 정리된다
        self.assertEqual(row.row_labels, ("전기변환 기기류부문", "제품매출", "수배전반류", "수출"))
        self.assertEqual((row.value_num, row.fiscal_year), (113.0, 2024))
        self.assertEqual(rows[("내수", "제50기")].fiscal_year, 2023)

    def test_misaligned_table_is_flagged_not_dropped(self):
        doc = _doc("""<TITLE>1. 임원 및 직원 등의 현황</TITLE>
          <TABLE><THEAD><TR><TD>구 분</TD><TD>인원수</TD><TD>연간급여 총액</TD><TD>1인평균 급여액</TD></TR></THEAD>
          <TBODY>
            <TR><TD>남</TD><TD>사무직</TD><TD>120</TD><TD>9,000,000,000</TD></TR>
            <TR><TD>여</TD><TD>사무직</TD><TD>80</TD><TD>5,000,000,000</TD></TR>
            <TR><TD>합계</TD><TD>사무직</TD><TD>200</TD><TD>14,000,000,000</TD></TR>
          </TBODY></TABLE>""")
        forms = form_tables(doc, report_year=2025)
        self.assertEqual(forms[0].status, "MISALIGNED")
        self.assertTrue(forms[0].misaligned_reason.startswith("non_numeric_column:인원수"))
        self.assertTrue(forms[0].rows, "값은 남긴다")
        self.assertTrue(all(r.parse_status == "MISALIGNED" for r in forms[0].rows))

    def test_shifted_equity_investment_row_is_flagged_by_column_pattern(self):
        # 덕산테코피아 실측: 상장여부·최초취득일자 칸이 빠져 값이 두 칸 앞으로 밀린 행
        doc = _doc("""<TITLE>3. 타법인출자 현황(상세)</TITLE>
          <TABLE><THEAD><TR><TD>법인명</TD><TD>상장여부</TD><TD>최초취득일자</TD><TD>출자목적</TD><TD>최초취득금액</TD><TD>기말잔액</TD></TR></THEAD>
          <TBODY>
            <TR><TD>BNA Corp.</TD><TD>사업 다각화</TD><TD>1,219</TD><TD>400</TD><TD>40.00</TD><TD>-</TD></TR>
            <TR><TD>CNA Corp.</TD><TD>경영참여</TD><TD>2,000</TD><TD>300</TD><TD>10.00</TD><TD>-</TD></TR>
          </TBODY></TABLE>""")
        forms = form_tables(doc, report_year=2025)
        self.assertEqual(forms[0].status, "MISALIGNED")
        self.assertEqual(forms[0].misaligned_reason, "pattern_mismatch:상장여부")

    def test_two_digit_year_dates_are_accepted(self):
        # POSCO홀딩스 실측: 최초취득일자가 '22.03 형식이라 날짜로 인정해야 열 밀림으로 오판하지 않는다
        doc = _doc("""<TITLE>3. 타법인출자 현황(상세)</TITLE>
          <TABLE><THEAD><TR><TD>법인명</TD><TD>상장여부</TD><TD>최초취득일자</TD><TD>출자목적</TD><TD>최초취득금액</TD><TD>기말잔액</TD></TR></THEAD>
          <TBODY>
            <TR><TD>(주)포스코</TD><TD>비상장</TD><TD>'22.03</TD><TD>경영참여</TD><TD>29,699,590</TD><TD>29,699,590</TD></TR>
            <TR><TD>포스코플랜텍</TD><TD>비상장</TD><TD>'10.06</TD><TD>단순투자</TD><TD>19,437</TD><TD>19,437</TD></TR>
          </TBODY></TABLE>""")
        self.assertEqual(form_tables(doc, report_year=2025)[0].status, "OK")

    def test_footnote_only_table_is_not_a_form(self):
        doc = _doc("""<TITLE>1. 임원 및 직원 등의 현황</TITLE>
          <TABLE><TBODY><TR><TD>※ 상기 직원수는 등기임원 제외 기준이며 1인평균급여액은 월평균 인원수로 나눈 값입니다. 평균근속연수 산정 기준은 다음과 같습니다.</TD></TR></TBODY></TABLE>""")
        self.assertEqual(form_tables(doc, report_year=2025), [])

    def test_non_form_tables_are_ignored(self):
        doc = _doc("""<TITLE>3. 연결재무제표 주석</TITLE>
          <TABLE><TBODY><TR><TD>과목</TD><TD>당기말</TD></TR><TR><TD>리스자산</TD><TD>3,306,464</TD></TR></TBODY></TABLE>""")
        self.assertEqual(form_tables(doc, report_year=2025), [])


if __name__ == "__main__":
    unittest.main()
