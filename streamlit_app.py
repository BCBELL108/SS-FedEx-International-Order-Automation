"""
FedEx International Shipping CSV Splitter - Streamlit Web App
==============================================================

Web interface for processing international shipment data for FedEx Ship Manager.

Author: Brandon Bell - SilverScreen Printing & Fulfillment
Version: 2.0.0
"""

import streamlit as st
import pandas as pd
import io
from pathlib import Path
import sys

# Add the script to path
sys.path.insert(0, str(Path(__file__).parent))

# Import the enhanced splitter
from fedex_csv_splitter_enhanced import (
    FedExCSVSplitterEnhanced,
    CountryCodeMapper,
    DataCleaner,
    AddressValidator
)

# Page configuration
st.set_page_config(
    page_title="FedEx CSV Splitter - SilverScreen",
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS - Dark theme
st.markdown("""
<style>
    /* Dark theme */
    .stApp {
        background-color: #0E1117;
    }
    
    /* Main header styling */
    .main-header {
        font-size: 2.2rem;
        color: #FFFFFF;
        text-align: center;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
        font-weight: 600;
    }
    
    .sub-header {
        font-size: 1.1rem;
        color: #AAAAAA;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    /* Success/Warning/Error boxes - dark theme */
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #1E3A1E;
        border: 1px solid #2E5A2E;
        color: #90EE90;
    }
    
    .warning-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #3A3A1E;
        border: 1px solid #5A5A2E;
        color: #FFD700;
    }
    
    .error-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #3A1E1E;
        border: 1px solid #5A2E2E;
        color: #FF6B6B;
    }
    
    /* Override Streamlit's default text colors for dark theme */
    .stMarkdown, .stText {
        color: #FFFFFF;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #1E1E1E;
    }
    
    .stTabs [data-baseweb="tab"] {
        color: #AAAAAA;
    }
    
    .stTabs [aria-selected="true"] {
        color: #FFFFFF;
    }
</style>
""", unsafe_allow_html=True)

# Logo and Header
logo_path = Path(__file__).parent / "SSlogo.png"
if logo_path.exists():
    col1, col2, col3 = st.columns([2, 3, 2])
    with col2:
        st.image(str(logo_path), use_container_width=True)
else:
    st.warning("Logo file not found: SSlogo.png")

st.markdown('<div class="main-header">FedEx International Shipping CSV Splitter</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Process international shipment data for FedEx Ship Manager</div>', unsafe_allow_html=True)

# Sidebar with instructions
with st.sidebar:
    st.header("Instructions")
    st.markdown("""
    **1. Upload File**
    - Excel (.xlsx, .xls) or CSV format
    - Must contain 31 columns (A-AE)
    
    **2. Review Data**
    - Check for validation errors
    - Review country code conversions
    - Verify declared values
    
    **3. Download Files**
    - IntFedExRec.csv (recipients)
    - IntFedExCom.csv (commodities)
    - validation_report.txt
    
    **Features:**
    - Address validation
    - Country code standardization
    - Declared value calculation
    - CSV-safe formatting
    - Comma removal
    """)
    
    st.divider()
    
    st.header("Country Codes")
    with st.expander("View supported countries"):
        st.markdown("""
        **Auto-converts to ISO codes:**
        - United Kingdom → GB
        - United States → US
        - England, Scotland, Wales → GB
        - Holland → NL
        - UAE, Dubai → AE
        - And 50+ more...
        """)

# Main content
tab1, tab2, tab3 = st.tabs(["Upload & Process", "Preview Data", "Validation Report"])

with tab1:
    st.header("Upload Your Shipment File")
    
    uploaded_file = st.file_uploader(
        "Choose an Excel or CSV file",
        type=['xlsx', 'xls', 'csv'],
        help="Upload your international shipment data file"
    )
    
    if uploaded_file is not None:
        # Save uploaded file temporarily
        temp_path = Path("/tmp") / uploaded_file.name
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"File uploaded: {uploaded_file.name} ({uploaded_file.size:,} bytes)")
        
        # Process button
        if st.button("Process File", type="primary"):
            with st.spinner("Processing..."):
                # Create output directory
                output_dir = Path("/tmp/fedex_output")
                output_dir.mkdir(exist_ok=True)
                
                # Process the file
                splitter = FedExCSVSplitterEnhanced(str(temp_path))
                
                # Store in session state for other tabs
                success = splitter.process(str(output_dir))
                
                if success:
                    # Store data in session state
                    st.session_state['splitter'] = splitter
                    st.session_state['recipient_csv'] = output_dir / "IntFedExRec.csv"
                    st.session_state['commodity_csv'] = output_dir / "IntFedExCom.csv"
                    st.session_state['validation_report'] = output_dir / "validation_report.txt"
                    st.session_state['processed'] = True
                    
                    # Read files into session state so downloads persist
                    with open(st.session_state['recipient_csv'], 'rb') as f:
                        st.session_state['recipient_csv_data'] = f.read()
                    with open(st.session_state['commodity_csv'], 'rb') as f:
                        st.session_state['commodity_csv_data'] = f.read()
                    with open(st.session_state['validation_report'], 'rb') as f:
                        st.session_state['validation_report_data'] = f.read()
                    
                    st.markdown('<div class="success-box"><strong>Success!</strong> Files processed successfully.</div>', unsafe_allow_html=True)
                    
                    # Show summary
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Rows", len(splitter.df))
                    with col2:
                        st.metric("Recipients", splitter.df['REFERENCE # (Recipient 1, 2, etc.)'].nunique())
                    with col3:
                        error_count = len(splitter.validation_errors)
                        st.metric("Validation Errors", error_count, 
                                 delta="Review Required" if error_count > 0 else "All Good",
                                 delta_color="inverse" if error_count > 0 else "normal")
                    
                    # Show warnings if any
                    if splitter.validation_warnings:
                        st.warning(f"{len(splitter.validation_warnings)} warnings found - check validation report")
                    
                    # Show errors if any
                    if splitter.validation_errors:
                        st.error(f"{len(splitter.validation_errors)} errors found - review required before import")
                        with st.expander("View Errors"):
                            for error in splitter.validation_errors:
                                st.write(f"• {error}")
                
                else:
                    st.error("Processing failed - check the error messages above")
    
    # Show download buttons if files have been processed (even after clicking download)
    if 'processed' in st.session_state and st.session_state['processed']:
        st.divider()
        st.subheader("Download Files")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.download_button(
                label="IntFedExRec.csv",
                data=st.session_state['recipient_csv_data'],
                file_name="IntFedExRec.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_recipient"
            )
        
        with col2:
            st.download_button(
                label="IntFedExCom.csv",
                data=st.session_state['commodity_csv_data'],
                file_name="IntFedExCom.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_commodity"
            )
        
        with col3:
            st.download_button(
                label="Validation Report",
                data=st.session_state['validation_report_data'],
                file_name="validation_report.txt",
                mime="text/plain",
                use_container_width=True,
                key="download_report"
            )

with tab2:
    st.header("Data Preview")
    
    if 'processed' in st.session_state and st.session_state['processed']:
        splitter = st.session_state['splitter']
        
        st.subheader("Original Data")
        st.dataframe(splitter.df, use_container_width=True, height=300)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Recipient Data Preview")
            st.dataframe(splitter.recipient_df.head(10), use_container_width=True)
        
        with col2:
            st.subheader("Commodity Data Preview")
            st.dataframe(splitter.commodity_df.head(10), use_container_width=True)
        
        # Show data cleaning summary
        st.divider()
        st.subheader("Data Cleaning Summary")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Text Fields Cleaned:**")
            st.write("• Commas removed")
            st.write("• Special characters sanitized")
            st.write("• Whitespace normalized")
        
        with col2:
            st.write("**Standardizations:**")
            st.write("• Country codes converted to ISO")
            st.write("• Phone numbers cleaned")
            st.write("• Postal codes formatted")
        
    else:
        st.info("Upload and process a file to preview data")

with tab3:
    st.header("Validation Report")
    
    if 'processed' in st.session_state and st.session_state['processed']:
        # Read and display validation report
        report_content = st.session_state['validation_report_data'].decode('utf-8')
        
        st.text_area("Full Validation Report", report_content, height=400)
        
        # Summary metrics
        splitter = st.session_state['splitter']
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Errors", len(splitter.validation_errors))
        with col2:
            st.metric("Warnings", len(splitter.validation_warnings))
        with col3:
            status = "PASS" if len(splitter.validation_errors) == 0 else "REVIEW REQUIRED"
            st.metric("Status", status)
        
        # Show detailed issues
        if splitter.validation_errors:
            st.error("Validation Errors")
            for error in splitter.validation_errors:
                st.write(f"• {error}")
        
        if splitter.validation_warnings:
            st.warning("Warnings")
            for warning in splitter.validation_warnings:
                st.write(f"• {warning}")
        
        if not splitter.validation_errors and not splitter.validation_warnings:
            st.success("No validation issues found - ready for FedEx import!")
    
    else:
        st.info("Upload and process a file to view validation report")

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.9rem;'>
    FedEx CSV Splitter v2.0 | Built by Brandon Bell | SilverScreen Printing & Fulfillment
</div>
""", unsafe_allow_html=True)
