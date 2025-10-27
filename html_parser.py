"""
HTML Parser for Bhulekha RoR (Record of Rights) Documents

This module provides deterministic parsing of Bhulekha website HTML to extract
structured Khatiyan land record information without requiring LLM API calls.

Extracted Information:
- Location: district, tehsil, village, khatiyan_number (both Odia and English)
- Owner: owner_name, father_name, caste
- Plots: total_plots, plot_numbers, total_area, land_type
- Metadata: dates, police station, revenue (in special_comments)
- Plot Notes: Special notes against individual plots (if present)
"""

from bs4 import BeautifulSoup
import re
import logging
import time
import os
from typing import Dict, Tuple, List, Optional

logger = logging.getLogger(__name__)


class BhulekhaHTMLParser:
    """Parser for Bhulekha RoR HTML documents"""

    def __init__(self, html_content: str):
        """
        Initialize parser with HTML content

        Args:
            html_content: Raw HTML string from Bhulekha webpage
        """
        self.html_content = html_content
        self.soup = BeautifulSoup(html_content, 'lxml')

        # Debug: Check HTML content (optional, set via environment variable)
        debug_mode = os.environ.get('BHULEKHA_DEBUG', '').lower() == 'true'

        if debug_mode:
            print(f"📊 HTML Stats: {len(html_content)} chars, {len(self.soup.find_all())} tags")
            if len(html_content) < 100:
                print(f"⚠️  WARNING: HTML content is very short: {html_content[:200]}")

            # Save HTML to file for inspection
            debug_dir = os.path.join(os.path.dirname(__file__), 'debug_html')
            os.makedirs(debug_dir, exist_ok=True)
            debug_file = os.path.join(debug_dir, f'debug_{int(time.time() * 1000)}.html')
            try:
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                logger.info(f"Debug: Saved HTML to {debug_file}")
                print(f"📁 Debug: Saved HTML to {debug_file}")
            except Exception as e:
                logger.warning(f"Could not save debug HTML: {e}")

    def extract_khatiyan_details(self) -> Tuple[Dict, str]:
        """
        Extract all Khatiyan details from HTML

        Returns:
            Tuple of (extraction_data dict, confidence_level string)
            confidence_level: "high", "medium", or "low"
        """
        try:
            # Extract all sections
            location_data = self._extract_location_info()
            plot_data = self._extract_plot_data()
            special_comments = self._extract_special_comments()

            # Merge all extracted data
            extraction_data = {
                **location_data,
                **plot_data,
                "special_comments": special_comments
            }

            # Calculate confidence based on completeness
            confidence = self._calculate_confidence(extraction_data)

            # Only print debug info if in debug mode
            debug_mode = os.environ.get('BHULEKHA_DEBUG', '').lower() == 'true'
            if not debug_mode:
                # Clean output for production
                print(f"✅ Parser extracted data with {confidence} confidence")
            else:
                # Verbose output for debugging
                print(f"location_data : {location_data}")
                print(f"plot_data : {plot_data}")
                print(f"special_comments : {special_comments}")

            logger.info(f"HTML parser extracted data with {confidence} confidence")
            return extraction_data, confidence

        except Exception as e:
            logger.error(f"Error in HTML parsing: {e}", exc_info=True)
            # Return minimal data with low confidence on error
            return {
                "district": "Extraction failed",
                "tehsil": "Extraction failed",
                "village": "Extraction failed",
                "khatiyan_number": "Extraction failed",
                "owner_name": "Extraction failed",
                "father_name": "Extraction failed",
                "caste": "Extraction failed",
                "total_plots": "Extraction failed",
                "plot_numbers": "Extraction failed",
                "total_area": "Extraction failed",
                "land_type": "Extraction failed",
                "special_comments": "Extraction failed",
                "other_owners": "Extraction failed"
            }, "low"

    def _extract_srorfront_field(self, label_odia: str, span_ids: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract field from SRoRFront_Uni.aspx format using span IDs

        Format: Label in <td>, value in <span id="...">Native Text</span>

        Args:
            label_odia: Odia label to search for (e.g., "ଜିଲ୍ଲା")
            span_ids: List of possible span IDs to check

        Returns:
            Tuple of (english_value, native_value) - note the reversed order!
        """
        try:
            debug_mode = os.environ.get('BHULEKHA_DEBUG', '').lower() == 'true'
            if debug_mode:
                print(f"🔍 Looking for SRoRFront field '{label_odia}' with IDs: {span_ids}")

            # Try to find by span ID first (most reliable)
            for span_id in span_ids:
                span = self.soup.find('span', id=span_id)
                if span:
                    value = span.get_text(strip=True)
                    if debug_mode:
                        print(f"   ✓ Found by ID '{span_id}': {value}")
                    return value, value

            # Fallback: search for label in td, then find associated span
            tds = self.soup.find_all('td')
            for td in tds:
                td_text = td.get_text(strip=True)
                if label_odia in td_text:
                    # Look for span in the same td or next td
                    span = td.find('span', class_='line')
                    if span:
                        value = span.get_text(strip=True)
                        if debug_mode:
                            print(f"   ✓ Found by label search: {value}")
                        return value, value

            if debug_mode:
                print(f"   ✗ SRoRFront field not found")
            return None, None

        except Exception as e:
            logger.warning(f"Error extracting SRoRFront field {label_odia}: {e}")
            if debug_mode:
                print(f"   ✗ Exception: {e}")
            return None, None

    def _extract_srorfront_khatiyan(self) -> Optional[str]:
        """
        Extract khatiyan number from SRoRFront_Uni.aspx format

        Looks for span with id containing 'lblKhatiyanslNo' or label "ଖତିୟାନର କ୍ରମିକ ନମ୍ବର"

        Returns:
            Khatiyan number or None
        """
        try:
            debug_mode = os.environ.get('BHULEKHA_DEBUG', '').lower() == 'true'
            if debug_mode:
                print(f"🔍 Looking for Khatiyan number in SRoRFront format...")

            # Try span ID
            span = self.soup.find('span', id=re.compile(r'lblKhatiyan.*No'))
            if span:
                value = span.get_text(strip=True)
                if debug_mode:
                    print(f"   ✓ Found khatiyan by ID: {value}")
                return value

            # Try by label
            tds = self.soup.find_all('td')
            for td in tds:
                td_text = td.get_text(strip=True)
                if "ଖତିୟାନର କ୍ରମିକ ନମ୍ବର" in td_text or "1) ଖତିୟାନର କ୍ରମିକ ନମ୍ବର" in td_text:
                    # Look for span in next td or same table
                    next_td = td.find_next_sibling('td')
                    if next_td:
                        span = next_td.find('span', class_='line')
                        if span:
                            value = span.get_text(strip=True)
                            if debug_mode:
                                print(f"   ✓ Found khatiyan by label: {value}")
                            return value

            if debug_mode:
                print(f"   ✗ Khatiyan number not found")
            return None

        except Exception as e:
            logger.warning(f"Error extracting SRoRFront khatiyan: {e}")
            if debug_mode:
                print(f"   ✗ Exception: {e}")
            return None

    def _extract_bilingual_field(self, label_odia: str, label_english: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract bilingual field (Odia and English) from location section

        Format: <strong>Odia / English</strong> : Odia Value / English Value

        Args:
            label_odia: Odia label text (e.g., "ଜିଲ୍ଲା")
            label_english: English label text (e.g., "District")

        Returns:
            Tuple of (native_value, english_value)
        """
        try:
            debug_mode = os.environ.get('BHULEKHA_DEBUG', '').lower() == 'true'
            # Find all strong tags containing labels
            strong_tags = self.soup.find_all('strong')
            if debug_mode:
                print(f"🔍 Looking for '{label_odia}' / '{label_english}' in {len(strong_tags)} strong tags")

            for strong in strong_tags:
                text = strong.get_text(strip=True)

                # Check if this strong tag contains our labels
                if label_odia in text or label_english in text:
                    if debug_mode:
                        print(f"   ✓ Found label in: {text[:100]}")
                    # Get the parent td and its sibling
                    td = strong.find_parent('td')
                    if td:
                        if debug_mode:
                            print(f"   ✓ Found parent <td>")
                        # Get the next sibling td which contains the value
                        value_td = td.find_next_sibling('td')
                        if value_td:
                            value_text = value_td.get_text(strip=True)
                            if debug_mode:
                                print(f"   ✓ Found value td: {value_text[:100]}")
                            # Remove leading colon and whitespace
                            value_text = value_text.lstrip(':').strip()

                            # Split by "/" to separate native and English values
                            parts = [p.strip() for p in value_text.split('/')]
                            if debug_mode:
                                print(f"   ✓ Split into {len(parts)} parts: {parts}")

                            if len(parts) >= 2:
                                native_value = parts[0]
                                english_value = parts[1]
                                if debug_mode:
                                    print(f"   ✓ Returning: native='{native_value}', english='{english_value}'")
                                return native_value, english_value
                            elif len(parts) == 1:
                                # Only one value present
                                if debug_mode:
                                    print(f"   ✓ Single value: '{parts[0]}'")
                                return None, parts[0]
                        else:
                            if debug_mode:
                                print(f"   ✗ No next sibling <td> found")
                    else:
                        if debug_mode:
                            print(f"   ✗ No parent <td> found")

            if debug_mode:
                print(f"   ✗ Label not found in any strong tags")
            return None, None

        except Exception as e:
            logger.warning(f"Error extracting bilingual field {label_english}: {e}")
            if debug_mode:
                print(f"   ✗ Exception: {e}")
            return None, None

    def _extract_location_info(self) -> Dict:
        """
        Extract location information (district, tehsil, village, khatiyan_number)

        Handles two different HTML formats:
        1. ViewRoR.aspx format: <strong>Label</strong> in <td>, value in next <td>
        2. SRoRFront_Uni.aspx format: Labels in <td>, values in <span> with IDs

        Returns:
            Dictionary with location fields (both native and English)
        """
        # Try Method 1: ViewRoR.aspx format (bilingual strong tags)
        native_district, district = self._extract_bilingual_field("ଜିଲ୍ଲା", "District")
        native_tehsil, tehsil = self._extract_bilingual_field("ତହସିଲ", "Tahasil")
        native_village, village = self._extract_bilingual_field("ମୌଜା", "Mouza")
        _, khatiyan_number = self._extract_bilingual_field("ଖତିୟାନର କ୍ରମିକ ନମ୍ବର", "Khata No")

        # If Method 1 failed, try Method 2: SRoRFront_Uni.aspx format (span IDs)
        if not district:
            debug_mode = os.environ.get('BHULEKHA_DEBUG', '').lower() == 'true'
            if debug_mode:
                print("🔄 Bilingual extraction failed, trying SRoRFront format...")
            district, native_district = self._extract_srorfront_field("ଜିଲ୍ଲା", ["gvfront_ctl02_lblDist"])
            tehsil, native_tehsil = self._extract_srorfront_field("ତହସିଲ", ["gvfront_ctl02_lblTehsil", "gvfront_ctl02_lblTahasil"])
            village, native_village = self._extract_srorfront_field("ମୌଜା", ["gvfront_ctl02_lblMouja"])
            khatiyan_number = self._extract_srorfront_khatiyan()

        return {
            "district": district or "Not found",
            "native_district": native_district,
            "tehsil": tehsil or "Not found",
            "native_tehsil": native_tehsil,
            "village": village or "Not found",
            "native_village": native_village,
            "khatiyan_number": khatiyan_number or "Not found"
        }

    def _extract_plot_data(self) -> Dict:
        """
        Extract plot information from the data table

        Handles two formats:
        1. ViewRoR.aspx: table id="GrdViewRoR" with columns
        2. SRoRFront_Uni.aspx: table id="gvRorBack" with different structure

        Returns:
            Dictionary with plot-related fields and owner information
        """
        try:
            # Try ViewRoR format first
            table = self.soup.find('table', id='GrdViewRoR')
            if not table:
                # Try SRoRFront format
                table = self.soup.find('table', id='gvRorBack')
                if table:
                    debug_mode = os.environ.get('BHULEKHA_DEBUG', '').lower() == 'true'
                    if debug_mode:
                        print("📊 Found gvRorBack table, using SRoRFront plot extraction")
                    return self._extract_srorfront_plot_data(table)
                else:
                    logger.warning("Plot table (GrdViewRoR or gvRorBack) not found in HTML")
                    return self._empty_plot_data()

            # Get all data rows (skip header)
            rows = table.find_all('tr')[1:]

            if not rows:
                logger.warning("No data rows found in plot table")
                return self._empty_plot_data()

            # Parse each row
            plots = []
            owners = set()
            fathers = set()
            castes = set()
            land_types = set()
            plot_types = set()
            total_area = 0.0

            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 11:  # Minimum required columns
                    continue

                try:
                    # Extract data from cells (0-indexed)
                    plot_number = cells[1].get_text(strip=True)  # Plot No
                    land_type = cells[2].get_text(strip=True)    # Plot Area Classification
                    plot_type = cells[3].get_text(strip=True)    # Plot Type
                    area_str = cells[4].get_text(strip=True)     # Area (Hec.)
                    owner = cells[8].get_text(strip=True)        # Tenant / Land Owner
                    father = cells[9].get_text(strip=True)       # Father's / Husband's Name
                    caste = cells[10].get_text(strip=True)       # Caste

                    # Parse area (handle potential formatting issues)
                    try:
                        area = float(area_str)
                        total_area += area
                    except ValueError:
                        logger.warning(f"Could not parse area: {area_str}")
                        area = 0.0

                    # Collect plot data
                    plot_info = {
                        "plot_number": plot_number,
                        "area": area,
                        "land_type": land_type,
                        "plot_type": plot_type,
                        "owner": owner,
                        "father": father,
                        "caste": caste
                    }

                    # Check for plot-specific notes (may be in additional columns)
                    if len(cells) > 13:
                        notes = cells[13].get_text(strip=True)
                        if notes and notes != '&nbsp;':
                            plot_info["notes"] = notes

                    plots.append(plot_info)

                    # Collect unique values
                    if owner:
                        owners.add(owner)
                    if father:
                        fathers.add(father)
                    if caste:
                        castes.add(caste)
                    if land_type:
                        land_types.add(land_type)
                    if plot_type:
                        plot_types.add(plot_type)

                except Exception as e:
                    logger.warning(f"Error parsing plot row: {e}")
                    continue

            # Aggregate data
            plot_numbers = ", ".join([p["plot_number"] for p in plots])

            # Handle multiple owners
            owners_list = sorted(list(owners))
            primary_owner = owners_list[0] if owners_list else "Not found"
            other_owners = ", ".join(owners_list[1:]) if len(owners_list) > 1 else "None mentioned"

            # Father's name (use first if multiple)
            father_name = list(fathers)[0] if fathers else "Not found"

            # Caste (use first if multiple)
            caste_name = list(castes)[0] if castes else "Not found"

            # Land type (aggregate all types, or use most common)
            land_type_str = " / ".join(sorted(list(land_types))) if land_types else "Not found"

            return {
                "total_plots": str(len(plots)),
                "plot_numbers": plot_numbers,
                "total_area": f"{total_area:.4f} hectares",
                "owner_name": primary_owner,
                "father_name": father_name,
                "caste": caste_name,
                "land_type": land_type_str,
                "other_owners": other_owners,
                "plots": plots  # Keep detailed plot info for potential future use
            }

        except Exception as e:
            logger.error(f"Error extracting plot data: {e}", exc_info=True)
            return self._empty_plot_data()

    def _extract_srorfront_plot_data(self, table) -> Dict:
        """
        Extract plot data from SRoRFront_Uni.aspx format (gvRorBack table)

        Also extracts owner information from the front page section (gvfront table)

        Returns:
            Dictionary with plot-related fields and owner information
        """
        try:
            plots = []
            plot_types = set()
            total_area = 0.0

            # Extract plot data from gvRorBack table
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 6:
                    continue

                # Check if this is a data row (not header or summary)
                first_cell_text = cells[0].get_text(strip=True)

                # Skip header rows and summary rows
                if not first_cell_text or first_cell_text.startswith('ପ୍ଲଟ') or 'plot' in first_cell_text.lower():
                    continue

                try:
                    # Extract plot number (first cell may contain link)
                    plot_link = cells[0].find('a')
                    plot_number = plot_link.get_text(strip=True) if plot_link else cells[0].get_text(strip=True)

                    # Skip if plot_number is empty or just whitespace
                    if not plot_number or plot_number == '&nbsp;':
                        continue

                    # Land type (column 2, index 1)
                    land_type = cells[1].get_text(strip=True) if len(cells) > 1 else ""

                    # Area - The columns are: Plot#, Land Type, Details, Acre, Decimal, Hectare, Remarks
                    # Try hectare column first (index 5), then calculate from Acre+Decimal if needed
                    area = 0.0

                    # Method 1: Try hectare column (index 5)
                    if len(cells) > 5:
                        hectare_str = cells[5].get_text(strip=True)
                        if hectare_str:
                            try:
                                area = float(hectare_str)
                            except ValueError:
                                pass

                    # Method 2: If hectare is empty, calculate from Acre (index 3) and Decimal (index 4)
                    if area == 0.0 and len(cells) > 4:
                        try:
                            acre_str = cells[3].get_text(strip=True)
                            decimal_str = cells[4].get_text(strip=True)

                            acre = float(acre_str) if acre_str else 0.0
                            decimal = float(decimal_str) if decimal_str else 0.0

                            # Convert to hectares: 1 acre = 0.404686 hectares, 1 decimal = 0.00404686 hectares
                            area = (acre * 0.404686) + (decimal * 0.00404686)
                        except ValueError:
                            area = 0.0

                    total_area += area

                    # Extract plot remarks/notes (last column, index 6)
                    plot_notes = ""
                    if len(cells) > 6:
                        notes_text = cells[6].get_text(strip=True)
                        if notes_text and notes_text != '&nbsp;':
                            plot_notes = notes_text

                    plot_info = {
                        "plot_number": plot_number,
                        "area": area,
                        "land_type": land_type,
                        "notes": plot_notes
                    }
                    plots.append(plot_info)

                    if land_type:
                        plot_types.add(land_type)

                except Exception as e:
                    logger.warning(f"Error parsing SRoRFront plot row: {e}")
                    continue

            # Extract owner information from front page section (not from plot table)
            owner_name = "Not found"
            father_name = "Not found"
            caste = "Not found"

            # Look for owner info in gvfront table section
            # Pattern: "2) ପ୍ରଜାର ନାମ, ପିତାର ନାମ, ଜାତି ଓ ବାସସ୍ଥାନ"
            owner_span = self.soup.find('span', id=re.compile(r'.*lblName.*'))
            if owner_span:
                owner_text = owner_span.get_text(strip=True)
                # Parse pattern: "Name ପି: Father, Name2 ସ୍ଵା: Father2 ଜା: Caste ବା: Location"
                # Extract first name
                if owner_text:
                    parts = owner_text.split('ପି:')
                    if len(parts) > 0:
                        owner_name = parts[0].strip()

                    # Extract father name (after ପି: or ସ୍ଵା:)
                    if 'ପି:' in owner_text:
                        father_part = owner_text.split('ପି:')[1].split(',')[0].strip()
                        father_name = father_part.split('ଜା:')[0].split('ସ୍ଵା:')[0].strip()

                    # Extract caste (after ଜା:)
                    if 'ଜା:' in owner_text:
                        caste_part = owner_text.split('ଜା:')[1].split('ବା:')[0].strip()
                        caste = caste_part

            # Aggregate plot data
            plot_numbers = ", ".join([p["plot_number"] for p in plots])
            land_type_str = " / ".join(sorted(list(plot_types))) if plot_types else "Not found"

            return {
                "total_plots": str(len(plots)) if plots else "Not found",
                "plot_numbers": plot_numbers if plot_numbers else "Not found",
                "total_area": f"{total_area:.4f} hectares" if total_area > 0 else "Not found",
                "owner_name": owner_name,
                "father_name": father_name,
                "caste": caste,
                "land_type": land_type_str,
                "other_owners": "None mentioned",  # SRoRFront format doesn't clearly separate multiple owners
                "plots": plots
            }

        except Exception as e:
            logger.error(f"Error extracting SRoRFront plot data: {e}", exc_info=True)
            return self._empty_plot_data()

    def _empty_plot_data(self) -> Dict:
        """Return empty plot data structure"""
        return {
            "total_plots": "Not found",
            "plot_numbers": "Not found",
            "total_area": "Not found",
            "owner_name": "Not found",
            "father_name": "Not found",
            "caste": "Not found",
            "land_type": "Not found",
            "other_owners": "Not found",
            "plots": []
        }

    def _extract_special_comments(self) -> str:
        """
        Extract metadata and special comments (dates, police station, revenue)

        Returns:
            Formatted string with all special comments/metadata
        """
        try:
            comments = []

            # Find the metadata section (after plot table, before buttons)
            # Look for the table containing special fields
            strong_tags = self.soup.find_all('strong')

            metadata_fields = {
                "Final Publication Date": ("ଅନ୍ତିମ ପ୍ରକାଶନ ତାରିଖ", "Final Publication Date"),
                "Rent Fixation Date": ("ଭଡା ନିର୍ଦ୍ଧାରଣ ତାରିଖ", "Rent Fixation Date"),
                "Police Station": ("ଥାନା", "Police Station"),
                "P.S. No.": ("ଥାନା ନଂ", "P.S. No"),
                "Tahasil No.": ("ତହସିଲ ନଂ", "Tahasil No"),
                "Land Revenue": ("ଜମି ରାଜସ୍ୱ", "Land Revenue")
            }

            for field_key, (odia_label, english_label) in metadata_fields.items():
                for strong in strong_tags:
                    text = strong.get_text(strip=True)
                    if odia_label in text or english_label in text:
                        # Get the text after the strong tag (usually after ":")
                        parent = strong.find_parent()
                        if parent:
                            full_text = parent.get_text(strip=True)
                            # Extract value after the label
                            match = re.search(r':\s*(.+?)(?:\n|$|<)', full_text)
                            if match:
                                value = match.group(1).strip()
                                comments.append(f"{english_label}: {value}")
                                break

            # Note: Plot-specific notes are stored in the plots array, not in special_comments
            # Special comments here are only for RoR-level metadata

            return "\n".join(comments) if comments else "No special comments found"

        except Exception as e:
            logger.error(f"Error extracting special comments: {e}", exc_info=True)
            return "Error extracting metadata"

    def _calculate_confidence(self, data: Dict) -> str:
        """
        Calculate confidence level based on completeness of extracted data

        Args:
            data: Extracted data dictionary

        Returns:
            Confidence level: "high", "medium", or "low"
        """
        # Define required fields for high confidence
        required_fields = [
            "district", "tehsil", "village", "khatiyan_number",
            "owner_name", "father_name", "caste",
            "total_plots", "plot_numbers", "total_area"
        ]

        # Count how many required fields are present and valid
        present_count = 0
        for field in required_fields:
            value = data.get(field, "")
            if value and value not in ["Not found", "Extraction failed", ""]:
                present_count += 1

        # Calculate completeness ratio
        completeness = present_count / len(required_fields)

        # Determine confidence level
        if completeness >= 0.95:  # At least 95% of fields present
            confidence = "high"
        elif completeness >= 0.70:  # At least 70% of fields present
            confidence = "medium"
        else:
            confidence = "low"

        logger.info(f"Parser confidence: {confidence} ({present_count}/{len(required_fields)} fields present)")
        return confidence


# Helper function for easy import
def parse_bhulekha_html(html_content: str) -> Tuple[Dict, str]:
    """
    Convenience function to parse Bhulekha HTML

    Args:
        html_content: Raw HTML string

    Returns:
        Tuple of (extraction_data dict, confidence_level string)
    """
    parser = BhulekhaHTMLParser(html_content)
    return parser.extract_khatiyan_details()
