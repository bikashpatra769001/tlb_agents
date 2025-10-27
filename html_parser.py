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
            # Find all strong tags containing labels
            strong_tags = self.soup.find_all('strong')

            for strong in strong_tags:
                text = strong.get_text(strip=True)

                # Check if this strong tag contains our labels
                if label_odia in text or label_english in text:
                    # Get the parent td and its sibling
                    td = strong.find_parent('td')
                    if td:
                        # Get the next sibling td which contains the value
                        value_td = td.find_next_sibling('td')
                        if value_td:
                            value_text = value_td.get_text(strip=True)
                            # Remove leading colon and whitespace
                            value_text = value_text.lstrip(':').strip()

                            # Split by "/" to separate native and English values
                            parts = [p.strip() for p in value_text.split('/')]

                            if len(parts) >= 2:
                                native_value = parts[0]
                                english_value = parts[1]
                                return native_value, english_value
                            elif len(parts) == 1:
                                # Only one value present
                                return None, parts[0]

            return None, None

        except Exception as e:
            logger.warning(f"Error extracting bilingual field {label_english}: {e}")
            return None, None

    def _extract_location_info(self) -> Dict:
        """
        Extract location information (district, tehsil, village, khatiyan_number)

        Returns:
            Dictionary with location fields (both native and English)
        """
        # Extract bilingual location fields
        native_district, district = self._extract_bilingual_field("ଜିଲ୍ଲା", "District")
        native_tehsil, tehsil = self._extract_bilingual_field("ତହସିଲ", "Tahasil")
        native_village, village = self._extract_bilingual_field("ମୌଜା", "Mouza")

        # Khatiyan number (usually only numeric, no Odia equivalent)
        _, khatiyan_number = self._extract_bilingual_field("ଖତିୟାନର କ୍ରମିକ ନମ୍ବର", "Khata No")

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
        Extract plot information from the data table (id="GrdViewRoR")

        Returns:
            Dictionary with plot-related fields and owner information
        """
        try:
            # Find the plot data table
            table = self.soup.find('table', id='GrdViewRoR')
            if not table:
                logger.warning("Plot table (GrdViewRoR) not found in HTML")
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

            # Check for any plot-specific notes
            plot_notes = []
            try:
                table = self.soup.find('table', id='GrdViewRoR')
                if table:
                    rows = table.find_all('tr')[1:]
                    for idx, row in enumerate(rows, 1):
                        cells = row.find_all('td')
                        if len(cells) > 13:
                            note = cells[13].get_text(strip=True)
                            if note and note != '&nbsp;' and note.lower() != 'not found':
                                plot_notes.append(f"Plot {cells[1].get_text(strip=True)}: {note}")
            except Exception as e:
                logger.warning(f"Error checking plot notes: {e}")

            if plot_notes:
                comments.append("Plot Notes: " + "; ".join(plot_notes))

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
