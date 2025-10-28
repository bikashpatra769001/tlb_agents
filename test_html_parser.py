"""
Unit tests for Bhulekha HTML Parser

Tests the HTML parser against the sample Bhulekha RoR HTML file
to ensure accurate extraction of all required fields.

Run with: python test_html_parser.py
"""

from html_parser import BhulekhaHTMLParser, parse_bhulekha_html


def test_parser_with_sample_html():
    """Test parser with actual sample Bhulekha HTML"""
    # Read the sample HTML file
    with open("sample_bhulekha.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    parser = BhulekhaHTMLParser(html_content)
    data_od, confidence = parser.extract_khatiyan_details()

    # Test Odia JSON - location information (with Odia keys)
    assert "ଜିଲ୍ଲା" in data_od, "Expected Odia key 'ଜିଲ୍ଲା' in Odia JSON"
    assert data_od["ଜିଲ୍ଲା"] is not None and len(data_od["ଜିଲ୍ଲା"]) > 0, \
        f"Expected Odia district value, got '{data_od['ଜିଲ୍ଲା']}'"
    assert "ତହସିଲ" in data_od, "Expected Odia key 'ତହସିଲ' in Odia JSON"
    assert data_od["ତହସିଲ"] is not None and len(data_od["ତହସିଲ"]) > 0, \
        f"Expected Odia tehsil value, got '{data_od['ତହସିଲ']}'"
    assert "ଗ୍ରାମ" in data_od, "Expected Odia key 'ଗ୍ରାମ' in Odia JSON"
    assert data_od["ଗ୍ରାମ"] is not None and len(data_od["ଗ୍ରାମ"]) > 0, \
        f"Expected Odia village value, got '{data_od['ଗ୍ରାମ']}'"
    assert "ଖତିୟାନ_ନମ୍ବର" in data_od, "Expected Odia key 'ଖତିୟାନ_ନମ୍ବର' in Odia JSON"

    # Test Odia JSON - owner information
    assert "ମାଲିକ_ନାମ" in data_od, "Expected Odia key 'ମାଲିକ_ନାମ' in Odia JSON"
    assert data_od["ମାଲିକ_ନାମ"] is not None and len(data_od["ମାଲିକ_ନାମ"]) > 0, \
        "Expected owner name in Odia JSON"
    assert "ଜାତି" in data_od, "Expected Odia key 'ଜାତି' in Odia JSON"

    # Test Odia JSON - plot information
    assert "ମୋଟ_ପ୍ଲଟ" in data_od, "Expected Odia key 'ମୋଟ_ପ୍ଲଟ' in Odia JSON"
    assert data_od["ମୋଟ_ପ୍ଲଟ"] is not None and len(data_od["ମୋଟ_ପ୍ଲଟ"]) > 0, \
        f"Expected total plots in Odia JSON"
    assert "ପ୍ଲଟ_ନମ୍ବର" in data_od, "Expected Odia key 'ପ୍ଲଟ_ନମ୍ବର' in Odia JSON"
    assert "ମୋଟ_କ୍ଷେତ୍ରଫଳ" in data_od, "Expected Odia key 'ମୋଟ_କ୍ଷେତ୍ରଫଳ' in Odia JSON"
    assert "hectares" in data_od["ମୋଟ_କ୍ଷେତ୍ରଫଳ"], \
        f"Expected total area in hectares in Odia JSON"

    # Test land type and other fields
    assert "ଜମି_ପ୍ରକାର" in data_od, "Expected Odia key 'ଜମି_ପ୍ରକାର' in Odia JSON"
    assert "ଅନ୍ୟ_ମାଲିକ" in data_od, "Expected Odia key 'ଅନ୍ୟ_ମାଲିକ' in Odia JSON"
    assert "ବିଶେଷ_ମନ୍ତବ୍ୟ" in data_od, "Expected Odia key 'ବିଶେଷ_ମନ୍ତବ୍ୟ' in Odia JSON"

    # Test confidence level (medium is acceptable if plot table is missing)
    assert confidence in ["high", "medium"], f"Expected 'high' or 'medium' confidence, got '{confidence}'"

    print("✅ All tests passed!")


def test_parser_confidence_calculation():
    """Test that confidence is calculated correctly based on field completeness"""
    # Create minimal HTML with all required fields
    html_with_all_fields = """
    <html>
    <body>
        <table>
            <tr><td><strong>ଜିଲ୍ଲା / District</strong></td><td>: Test District / Test</td></tr>
            <tr><td><strong>ତହସିଲ / Tahasil</strong></td><td>: Test Tahasil / Test</td></tr>
            <tr><td><strong>ମୌଜା / Mouza</strong></td><td>: Test Village / Test</td></tr>
            <tr><td><strong>ଖତିୟାନର କ୍ରମିକ ନମ୍ବର / Khata No.</strong></td><td>: 123</td></tr>
        </table>
        <table id="GrdViewRoR">
            <tr><th>Sl No</th><th>Plot No</th><th>Area</th><th>Owner</th><th>Father</th><th>Caste</th></tr>
            <tr>
                <td>1</td><td>1</td><td></td><td></td><td>0.5</td><td></td><td></td><td></td>
                <td>Test Owner</td><td>Test Father</td><td>Test Caste</td>
            </tr>
        </table>
    </body>
    </html>
    """

    parser = BhulekhaHTMLParser(html_with_all_fields)
    data_od, confidence = parser.extract_khatiyan_details()

    # Should have high confidence with all required fields
    assert confidence == "high", f"Expected 'high' confidence with complete data, got '{confidence}'"


def test_parser_with_missing_fields():
    """Test parser behavior when some fields are missing"""
    # Create HTML with missing plot table
    html_with_missing_table = """
    <html>
    <body>
        <table>
            <tr><td><strong>ଜିଲ୍ଲା / District</strong></td><td>: Test / Test</td></tr>
            <tr><td><strong>ତହସିଲ / Tahasil</strong></td><td>: Test / Test</td></tr>
        </table>
    </body>
    </html>
    """

    parser = BhulekhaHTMLParser(html_with_missing_table)
    data_od, confidence = parser.extract_khatiyan_details()

    # Should have low confidence with missing fields
    assert confidence in ["low", "medium"], \
        f"Expected 'low' or 'medium' confidence with missing data, got '{confidence}'"

    # Should still return "Not found" for missing fields in Odia JSON
    assert data_od.get("ମାଲିକ_ନାମ") == "Not found", "Expected 'Not found' for owner_name"
    assert data_od.get("ମୋଟ_ପ୍ଲଟ") == "Not found", "Expected 'Not found' for total_plots"


def test_bilingual_field_extraction():
    """Test that bilingual fields are correctly split"""
    html = """
    <html>
    <body>
        <table>
            <tr><td><strong>ଜିଲ୍ଲା / District</strong></td><td>: କଟକ / Cuttack</td></tr>
        </table>
    </body>
    </html>
    """

    parser = BhulekhaHTMLParser(html)
    native, english = parser._extract_bilingual_field("ଜିଲ୍ଲା", "District")

    assert native == "କଟକ", f"Expected Odia 'କଟକ', got '{native}'"
    assert english == "Cuttack", f"Expected English 'Cuttack', got '{english}'"


def test_plot_data_aggregation():
    """Test that multiple plots are correctly aggregated"""
    html = """
    <html>
    <body>
        <table id="GrdViewRoR">
            <tr><th>Sl</th><th>Plot No</th><th>Type</th><th>Type2</th><th>Area</th><th>R1</th><th>R2</th><th>R3</th>
                <th>Owner</th><th>Father</th><th>Caste</th></tr>
            <tr><td>1</td><td>100</td><td>Type1</td><td>Type2</td><td>0.5</td><td></td><td></td><td></td>
                <td>Owner1</td><td>Father1</td><td>Caste1</td></tr>
            <tr><td>2</td><td>200</td><td>Type1</td><td>Type2</td><td>0.3</td><td></td><td></td><td></td>
                <td>Owner1</td><td>Father1</td><td>Caste1</td></tr>
            <tr><td>3</td><td>300</td><td>Type1</td><td>Type2</td><td>0.2</td><td></td><td></td><td></td>
                <td>Owner2</td><td>Father2</td><td>Caste2</td></tr>
        </table>
    </body>
    </html>
    """

    parser = BhulekhaHTMLParser(html)
    plot_data = parser._extract_plot_data()

    assert plot_data["total_plots"] == "3", f"Expected 3 plots, got '{plot_data['total_plots']}'"
    assert "1.0000" in plot_data["total_area"], f"Expected total area ~1.0, got '{plot_data['total_area']}'"
    assert "100" in plot_data["plot_numbers"] and "200" in plot_data["plot_numbers"], \
        "Expected plot numbers 100, 200, 300"
    assert plot_data["owner_name"] in ["Owner1", "Owner2"], "Expected one of the owners as primary"
    assert "Owner" in plot_data["other_owners"], "Expected other owners to be listed"


def test_special_comments_extraction():
    """Test metadata extraction from special comments section"""
    html = """
    <html>
    <body>
        <table>
            <tr><td><strong>ଅନ୍ତିମ ପ୍ରକାଶନ ତାରିଖ / Final Publication Date</strong> : 29/03/2003</td></tr>
            <tr><td><strong>ଥାନା/ Police Station</strong> : Lalbag</td></tr>
            <tr><td><strong>ଜମି ରାଜସ୍ୱ/ Land Revenue</strong> : 6.40</td></tr>
        </table>
    </body>
    </html>
    """

    parser = BhulekhaHTMLParser(html)
    comments = parser._extract_special_comments()

    assert "29/03/2003" in comments, "Expected publication date in comments"
    assert "Lalbag" in comments, "Expected police station in comments"
    assert "6.40" in comments, "Expected land revenue in comments"


def test_convenience_function():
    """Test the convenience function for parsing"""
    with open("sample_bhulekha.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    data_od, confidence = parse_bhulekha_html(html_content)

    assert data_od is not None, "Expected Odia data to be returned"
    assert confidence in ["high", "medium", "low"], f"Expected valid confidence level, got '{confidence}'"
    assert "ଜିଲ୍ଲା" in data_od, "Expected Odia keys in Odia JSON"
    assert data_od["ଜିଲ୍ଲା"] is not None and len(data_od["ଜିଲ୍ଲା"]) > 0, "Expected Odia district value"


if __name__ == "__main__":
    # Run tests manually
    print("Running HTML Parser Tests...")
    print("=" * 80)

    try:
        test_parser_with_sample_html()
        print("\n✅ test_parser_with_sample_html PASSED")
    except AssertionError as e:
        print(f"\n❌ test_parser_with_sample_html FAILED: {e}")

    try:
        test_parser_confidence_calculation()
        print("✅ test_parser_confidence_calculation PASSED")
    except AssertionError as e:
        print(f"❌ test_parser_confidence_calculation FAILED: {e}")

    try:
        test_parser_with_missing_fields()
        print("✅ test_parser_with_missing_fields PASSED")
    except AssertionError as e:
        print(f"❌ test_parser_with_missing_fields FAILED: {e}")

    try:
        test_bilingual_field_extraction()
        print("✅ test_bilingual_field_extraction PASSED")
    except AssertionError as e:
        print(f"❌ test_bilingual_field_extraction FAILED: {e}")

    try:
        test_plot_data_aggregation()
        print("✅ test_plot_data_aggregation PASSED")
    except AssertionError as e:
        print(f"❌ test_plot_data_aggregation FAILED: {e}")

    try:
        test_special_comments_extraction()
        print("✅ test_special_comments_extraction PASSED")
    except AssertionError as e:
        print(f"❌ test_special_comments_extraction FAILED: {e}")

    try:
        test_convenience_function()
        print("✅ test_convenience_function PASSED")
    except AssertionError as e:
        print(f"❌ test_convenience_function FAILED: {e}")

    print("\n" + "=" * 80)
    print("Tests completed!")
