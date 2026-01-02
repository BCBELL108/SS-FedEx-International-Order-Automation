#!/usr/bin/env python3
"""
Enhanced FedEx International Shipping CSV Splitter
===================================================

Features:
- Data cleaning (removes commas, special characters)
- Country code standardization (handles full names and abbreviations)
- Address validation
- Declared value auto-calculation and verification
- Reference number validation
- CSV-safe output formatting

Usage:
    python fedex_csv_splitter_enhanced.py <input_file> [output_dir]

Author: Brandon Bell - SilverScreen Printing & Fulfillment
Version: 2.0.0
"""

import sys
import os
import pandas as pd
import re
from pathlib import Path
from typing import Tuple, Dict, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class CountryCodeMapper:
    """Handles country name to ISO code conversion."""
    
    # Comprehensive country code mapping
    COUNTRY_CODES = {
        # North America
        'UNITED STATES': 'US', 'USA': 'US', 'U.S.A': 'US', 'U.S.': 'US',
        'CANADA': 'CA', 'MEXICO': 'MX',
        
        # Europe
        'UNITED KINGDOM': 'GB', 'UK': 'GB', 'GREAT BRITAIN': 'GB', 'ENGLAND': 'GB',
        'SCOTLAND': 'GB', 'WALES': 'GB', 'NORTHERN IRELAND': 'GB',
        'FRANCE': 'FR', 'GERMANY': 'DE', 'SPAIN': 'ES', 'ITALY': 'IT',
        'NETHERLANDS': 'NL', 'HOLLAND': 'NL', 'BELGIUM': 'BE', 'SWITZERLAND': 'CH',
        'AUSTRIA': 'AT', 'SWEDEN': 'SE', 'NORWAY': 'NO', 'DENMARK': 'DK',
        'FINLAND': 'FI', 'IRELAND': 'IE', 'PORTUGAL': 'PT', 'GREECE': 'GR',
        'POLAND': 'PL', 'CZECH REPUBLIC': 'CZ', 'HUNGARY': 'HU', 'ROMANIA': 'RO',
        
        # Asia-Pacific
        'AUSTRALIA': 'AU', 'NEW ZEALAND': 'NZ', 'JAPAN': 'JP', 'CHINA': 'CN',
        'SOUTH KOREA': 'KR', 'KOREA': 'KR', 'SINGAPORE': 'SG', 'HONG KONG': 'HK',
        'TAIWAN': 'TW', 'THAILAND': 'TH', 'MALAYSIA': 'MY', 'INDONESIA': 'ID',
        'PHILIPPINES': 'PH', 'VIETNAM': 'VN', 'INDIA': 'IN',
        
        # Middle East
        'ISRAEL': 'IL', 'SAUDI ARABIA': 'SA', 'UAE': 'AE', 
        'UNITED ARAB EMIRATES': 'AE', 'DUBAI': 'AE',
        
        # South America
        'BRAZIL': 'BR', 'ARGENTINA': 'AR', 'CHILE': 'CL', 'COLOMBIA': 'CO',
        'PERU': 'PE', 'VENEZUELA': 'VE',
        
        # Africa
        'SOUTH AFRICA': 'ZA', 'EGYPT': 'EG', 'MOROCCO': 'MA', 'KENYA': 'KE',
    }
    
    @classmethod
    def standardize_country(cls, country: str) -> str:
        """
        Convert country name to standard 2-letter ISO code.
        
        Args:
            country: Country name or code (any format)
            
        Returns:
            Standardized 2-letter country code
        """
        if pd.isna(country) or not country:
            logger.warning("Empty country field detected")
            return "XX"  # Invalid placeholder
        
        # Clean and uppercase
        country_clean = str(country).strip().upper()
        
        # If already 2-letter code, validate and return
        if len(country_clean) == 2 and country_clean.isalpha():
            return country_clean
        
        # Look up in mapping
        if country_clean in cls.COUNTRY_CODES:
            return cls.COUNTRY_CODES[country_clean]
        
        # Log unknown country
        logger.warning(f"Unknown country format: '{country}' - using as-is")
        return country_clean[:2] if len(country_clean) >= 2 else "XX"


class DataCleaner:
    """Handles data cleaning and CSV-safe formatting."""
    
    @staticmethod
    def remove_commas(text: str) -> str:
        """Remove commas from text to prevent CSV column breaks."""
        if pd.isna(text):
            return ""
        return str(text).replace(',', '')
    
    @staticmethod
    def clean_text_field(text: str) -> str:
        """
        Clean text field for CSV safety.
        - Removes commas
        - Strips extra whitespace
        - Removes special characters that break ODBC
        """
        if pd.isna(text):
            return ""
        
        text = str(text)
        # Remove commas
        text = text.replace(',', '')
        # Remove line breaks
        text = text.replace('\n', ' ').replace('\r', ' ')
        # Remove tabs
        text = text.replace('\t', ' ')
        # Collapse multiple spaces
        text = re.sub(r'\s+', ' ', text)
        # Strip
        text = text.strip()
        
        return text
    
    @staticmethod
    def clean_phone_number(phone: str) -> str:
        """Clean phone number (remove spaces, dashes, parentheses)."""
        if pd.isna(phone):
            return ""
        phone = str(phone)
        # Keep only digits and plus sign
        phone = re.sub(r'[^\d+]', '', phone)
        return phone
    
    @staticmethod
    def clean_postal_code(postal: str) -> str:
        """Clean postal code (uppercase, remove extra spaces)."""
        if pd.isna(postal):
            return ""
        postal = str(postal).upper().strip()
        # Remove excessive spaces
        postal = re.sub(r'\s+', ' ', postal)
        return postal


class AddressValidator:
    """Basic address validation to catch common errors."""
    
    @staticmethod
    def validate_required_fields(row: pd.Series, field_name: str) -> Tuple[bool, str]:
        """
        Validate that required field is not empty.
        
        Returns:
            (is_valid, error_message)
        """
        value = row.get(field_name)
        if pd.isna(value) or str(value).strip() == "":
            return False, f"Missing required field: {field_name}"
        return True, ""
    
    @staticmethod
    def validate_address(row: pd.Series, ref_num: int) -> Tuple[bool, list]:
        """
        Validate recipient address fields.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        required_fields = [
            'SHIP TO ATTENTION (required)',
            'SHIP TO ADDRESS LINE 1 (required)',
            'CITY (required)',
            'COUNTRY (required)',
            'POSTAL CODE (required)',
        ]
        
        for field in required_fields:
            is_valid, error = AddressValidator.validate_required_fields(row, field)
            if not is_valid:
                errors.append(f"Ref#{ref_num}: {error}")
        
        # Validate phone number exists
        phone = row.get('RECIPIENT PHONE # (required)')
        if pd.isna(phone) or str(phone).strip() == "":
            errors.append(f"Ref#{ref_num}: Missing phone number")
        
        return len(errors) == 0, errors


class FedExCSVSplitterEnhanced:
    """Enhanced FedEx CSV splitter with validation and cleaning."""
    
    RECIPIENT_COLS_START = 0
    RECIPIENT_COLS_END = 21
    COMMODITY_COLS_START = 21
    COMMODITY_COLS_END = 31
    
    OUTPUT_RECIPIENT_FILENAME = "IntFedExRec.csv"
    OUTPUT_COMMODITY_FILENAME = "IntFedExCom.csv"
    OUTPUT_VALIDATION_REPORT = "validation_report.txt"
    
    def __init__(self, input_file: str):
        self.input_file = Path(input_file)
        self.df = None
        self.recipient_df = None
        self.commodity_df = None
        self.validation_errors = []
        self.validation_warnings = []
        
    def validate_input_file(self) -> bool:
        """Validate input file exists and has supported format."""
        if not self.input_file.exists():
            logger.error(f"Input file does not exist: {self.input_file}")
            return False
        
        valid_extensions = {'.xlsx', '.xls', '.csv'}
        if self.input_file.suffix.lower() not in valid_extensions:
            logger.error(f"Unsupported file format: {self.input_file.suffix}")
            return False
        
        logger.info(f"✓ Input file validated: {self.input_file}")
        return True
    
    def load_data(self) -> bool:
        """Load data from input file."""
        try:
            if self.input_file.suffix.lower() == '.csv':
                self.df = pd.read_csv(self.input_file)
            else:
                self.df = pd.read_excel(self.input_file)
            
            logger.info(f"✓ Data loaded: {len(self.df)} rows, {len(self.df.columns)} columns")
            return True
        except Exception as e:
            logger.error(f"Failed to load file: {e}")
            return False
    
    def clean_data(self) -> bool:
        """Clean and standardize all data fields."""
        try:
            logger.info("Cleaning and standardizing data...")
            
            # Clean text fields (remove commas, special chars)
            text_columns = [
                'SHIP TO ATTENTION (required)',
                'RECIPIENT EMAIL (if applicable)',
                'COMPANY NAME (if applicable)',
                'SHIP TO ADDRESS LINE 1 (required)',
                'SHIP TO ADDRESS LINE 2 (if applicable)',
                'CITY (required)',
                'STATE / PROVINCE (if applicable)',
                'BILLING - 3RD PARTY COMPANY NAME (required)',
                'BILLING - 3RD PARTY ADDRESS 1 (required)',
                'BILLING - 3RD PARTY ADDRESS 2 (if applicable)',
                'BILLING - 3RD PARTY CITY (required)',
                'ITEM DESCRIPTION (required)',
                'STYLE # (required)',
            ]
            
            for col in text_columns:
                if col in self.df.columns:
                    self.df[col] = self.df[col].apply(DataCleaner.clean_text_field)
            
            # Clean phone numbers
            phone_col = 'RECIPIENT PHONE # (required)'
            if phone_col in self.df.columns:
                self.df[phone_col] = self.df[phone_col].apply(DataCleaner.clean_phone_number)
            
            # Clean postal codes
            postal_cols = ['POSTAL CODE (required)', 'BILLING - 3RD PARTY POSTAL CODE (required)']
            for col in postal_cols:
                if col in self.df.columns:
                    self.df[col] = self.df[col].apply(DataCleaner.clean_postal_code)
            
            # Standardize country codes
            country_col = 'COUNTRY (required)'
            if country_col in self.df.columns:
                original_countries = self.df[country_col].copy()
                self.df[country_col] = self.df[country_col].apply(CountryCodeMapper.standardize_country)
                
                # Log conversions
                changes = original_countries != self.df[country_col]
                if changes.any():
                    for idx in changes[changes].index:
                        logger.info(f"  Country standardized: '{original_countries[idx]}' → '{self.df.loc[idx, country_col]}'")
            
            logger.info("✓ Data cleaning complete")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clean data: {e}")
            return False
    
    def calculate_declared_values(self) -> bool:
        """Calculate and verify declared values."""
        try:
            logger.info("Calculating declared values...")
            
            qty_col = 'QUANTITY (required)'
            price_col = 'UNIT PRICE (required)'
            value_col = 'DECLARED VALUE (required)'
            
            # Calculate correct value
            self.df['_calculated_value'] = self.df[qty_col] * self.df[price_col]
            
            # Check for mismatches
            tolerance = 0.01
            self.df['_value_mismatch'] = (self.df[value_col] - self.df['_calculated_value']).abs() > tolerance
            
            mismatches = self.df[self.df['_value_mismatch']]
            if len(mismatches) > 0:
                logger.warning(f"Found {len(mismatches)} rows with incorrect declared values - fixing...")
                for idx, row in mismatches.iterrows():
                    ref = row['REFERENCE # (Recipient 1, 2, etc.)']
                    old_val = row[value_col]
                    new_val = row['_calculated_value']
                    self.validation_warnings.append(
                        f"Ref#{ref} Row{idx+2}: Declared value corrected {old_val:.2f} → {new_val:.2f}"
                    )
                
                # Update with calculated values
                self.df[value_col] = self.df['_calculated_value']
            
            # Clean up temp columns
            self.df = self.df.drop(columns=['_calculated_value', '_value_mismatch'])
            
            logger.info("✓ Declared values validated and corrected")
            return True
            
        except Exception as e:
            logger.error(f"Failed to calculate declared values: {e}")
            return False
    
    def validate_addresses(self) -> bool:
        """Validate all recipient addresses."""
        try:
            logger.info("Validating recipient addresses...")
            
            # Get unique reference numbers
            ref_col = 'REFERENCE # (Recipient 1, 2, etc.)'
            unique_refs = self.df[ref_col].unique()
            
            for ref_num in unique_refs:
                # Get first row for this reference (all rows should have same address)
                ref_rows = self.df[self.df[ref_col] == ref_num]
                first_row = ref_rows.iloc[0]
                
                is_valid, errors = AddressValidator.validate_address(first_row, ref_num)
                if not is_valid:
                    self.validation_errors.extend(errors)
            
            if self.validation_errors:
                logger.warning(f"⚠ Found {len(self.validation_errors)} address validation errors")
            else:
                logger.info("✓ All addresses validated successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to validate addresses: {e}")
            return False
    
    def split_data(self) -> bool:
        """Split data into recipient and commodity dataframes."""
        try:
            # Extract recipient columns
            self.recipient_df = self.df.iloc[:, self.RECIPIENT_COLS_START:self.RECIPIENT_COLS_END].copy()
            logger.info(f"✓ Extracted recipient data: {len(self.recipient_df.columns)} columns")
            
            # Extract commodity columns  
            self.commodity_df = self.df.iloc[:, self.COMMODITY_COLS_START:self.COMMODITY_COLS_END].copy()
            logger.info(f"✓ Extracted commodity data: {len(self.commodity_df.columns)} columns")
            
            return True
        except Exception as e:
            logger.error(f"Failed to split data: {e}")
            return False
    
    def save_csvs(self, output_dir: str = None) -> Tuple[bool, str, str]:
        """Save CSV files and validation report."""
        try:
            if output_dir is None:
                output_dir = self.input_file.parent
            else:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
            
            recipient_path = output_dir / self.OUTPUT_RECIPIENT_FILENAME
            commodity_path = output_dir / self.OUTPUT_COMMODITY_FILENAME
            report_path = output_dir / self.OUTPUT_VALIDATION_REPORT
            
            # Round numeric columns to 2 decimal places before saving
            numeric_cols = ['UNIT PRICE (required)', 'DECLARED VALUE (required)']
            for col in numeric_cols:
                if col in self.commodity_df.columns:
                    self.commodity_df[col] = self.commodity_df[col].round(2)
            
            # Save CSVs
            self.recipient_df.to_csv(recipient_path, index=False, encoding='utf-8')
            logger.info(f"✓ Saved: {recipient_path}")
            
            self.commodity_df.to_csv(commodity_path, index=False, encoding='utf-8', float_format='%.2f')
            logger.info(f"✓ Saved: {commodity_path}")
            
            # Save validation report
            self.save_validation_report(report_path)
            
            return True, str(recipient_path), str(commodity_path)
            
        except Exception as e:
            logger.error(f"Failed to save files: {e}")
            return False, "", ""
    
    def save_validation_report(self, report_path: Path):
        """Save validation report with errors and warnings."""
        with open(report_path, 'w') as f:
            f.write("=" * 70 + "\n")
            f.write("FedEx CSV Splitter - Validation Report\n")
            f.write("=" * 70 + "\n\n")
            
            f.write(f"Input File: {self.input_file}\n")
            f.write(f"Total Rows Processed: {len(self.df)}\n")
            f.write(f"Unique Recipients: {self.df['REFERENCE # (Recipient 1, 2, etc.)'].nunique()}\n\n")
            
            if self.validation_errors:
                f.write(f"ERRORS ({len(self.validation_errors)}):\n")
                f.write("-" * 70 + "\n")
                for error in self.validation_errors:
                    f.write(f"  ✗ {error}\n")
                f.write("\n")
            else:
                f.write("✓ No validation errors found\n\n")
            
            if self.validation_warnings:
                f.write(f"WARNINGS ({len(self.validation_warnings)}):\n")
                f.write("-" * 70 + "\n")
                for warning in self.validation_warnings:
                    f.write(f"  ⚠ {warning}\n")
                f.write("\n")
            else:
                f.write("✓ No warnings\n\n")
            
            f.write("=" * 70 + "\n")
            f.write("END OF REPORT\n")
        
        logger.info(f"✓ Validation report saved: {report_path}")
        
        # Print summary
        if self.validation_errors:
            logger.warning(f"⚠ {len(self.validation_errors)} ERRORS found - check validation_report.txt")
        if self.validation_warnings:
            logger.info(f"ℹ {len(self.validation_warnings)} warnings - check validation_report.txt")
    
    def process(self, output_dir: str = None) -> bool:
        """Execute complete processing pipeline."""
        logger.info("=" * 70)
        logger.info("Enhanced FedEx International CSV Splitter v2.0")
        logger.info("=" * 70)
        
        if not self.validate_input_file():
            return False
        
        if not self.load_data():
            return False
        
        if not self.clean_data():
            return False
        
        if not self.calculate_declared_values():
            return False
        
        if not self.validate_addresses():
            return False
        
        if not self.split_data():
            return False
        
        success, rec_path, com_path = self.save_csvs(output_dir)
        
        if success:
            logger.info("=" * 70)
            logger.info("✓ SUCCESS! Files created:")
            logger.info(f"  • Recipient CSV: {rec_path}")
            logger.info(f"  • Commodity CSV: {com_path}")
            if self.validation_errors:
                logger.warning(f"  ⚠ {len(self.validation_errors)} validation errors - review required")
            logger.info("=" * 70)
            return True
        
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python fedex_csv_splitter_enhanced.py <input_file> [output_dir]")
        print("Example: python fedex_csv_splitter_enhanced.py shipments.xlsx")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    splitter = FedExCSVSplitterEnhanced(input_file)
    success = splitter.process(output_dir)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
