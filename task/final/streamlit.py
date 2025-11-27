import warnings
warnings.filterwarnings('ignore')

import streamlit as st
from pathlib import Path
import tempfile
import os
from pdfixsdk import *
from working_file1 import (
    PdfTagTransformerPhase1, 
    Reference, 
    Table, 
    footprint,
    Table_delete,
    PdfAltTextSetter,
    Figure_inlineequation,
    formula_inside_figure_delete
)

# Initialize Pdfix
pdfix = GetPdfix()
if not pdfix:
    st.error("❌ Failed to initialize Pdfix")
    st.stop()


# Helper to save uploaded file temporarily
def save_uploaded_file(uploaded_file):
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, uploaded_file.name)
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return temp_path


# Title
st.title("📄 PDF Tag Transformer App")
st.write("Upload a PDF and all processing phases will run automatically")

# File uploader
uploaded_pdf = st.file_uploader("Upload a PDF to process", type=["pdf"])

if uploaded_pdf:
    input_pdf_path = save_uploaded_file(uploaded_pdf)
    st.success(f"✅ Uploaded: {uploaded_pdf.name}")
    
    # Create progress container
    progress_container = st.container()
    
    with progress_container:
        st.header("🔄 Processing...")
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        output_pdf_path = input_pdf_path
        total_phases = 8
        
        try:
            # Phase 1
            status_text.text("📘 Running Phase 1 (Steps 1–13)...")
            phase1_output = output_pdf_path.replace(".pdf", "_phase1.pdf")
            transformer = PdfTagTransformerPhase1(pdfix)
            transformer.modify_pdf_tags(output_pdf_path, phase1_output)
            output_pdf_path = phase1_output
            progress_bar.progress(1/total_phases)
            st.write("✅ Phase 1 complete")

            # Phase 2
            status_text.text("📘 Running Phase 2 – Reference (Steps 14–17)...")
            phase2_output = output_pdf_path.replace(".pdf", "_phase2.pdf")
            reference = Reference(pdfix)
            reference.modify_pdf_tags(output_pdf_path, phase2_output)
            output_pdf_path = phase2_output
            progress_bar.progress(2/total_phases)
            st.write("✅ Phase 2 complete")

            # Phase 3
            status_text.text("📘 Running Phase 3 – Table (Steps 18–24)...")
            phase3_output = output_pdf_path.replace(".pdf", "_phase3.pdf")
            table = Table(pdfix)
            table.modify_pdf_tags(output_pdf_path, phase3_output)
            output_pdf_path = phase3_output
            progress_bar.progress(3/total_phases)
            st.write("✅ Phase 3 complete")

            # Phase 4
            status_text.text("📘 Running Phase 4 – Footprint (Steps 25–30)...")
            phase4_output = output_pdf_path.replace(".pdf", "_phase4.pdf")
            fp = footprint(pdfix)
            fp.modify_pdf_tags(output_pdf_path, phase4_output)
            output_pdf_path = phase4_output
            progress_bar.progress(4/total_phases)
            st.write("✅ Phase 4 complete")

            # Phase 5
            status_text.text("📘 Running Phase 5 – Table Delete (Steps 30–40)...")
            phase5_output = output_pdf_path.replace(".pdf", "_phase5.pdf")
            fp = Table_delete(pdfix)
            fp.modify_pdf_tags(output_pdf_path, phase5_output)
            output_pdf_path = phase5_output
            progress_bar.progress(5/total_phases)
            st.write("✅ Phase 5 complete")

            # Phase 6
            status_text.text("📘 Running Phase 6 – Alt Text Formula (Steps 40–42)...")
            phase6_output = output_pdf_path.replace(".pdf", "_phase6.pdf")
            fp = PdfAltTextSetter(pdfix)
            fp.modify_pdf(output_pdf_path, phase6_output)
            output_pdf_path = phase6_output
            progress_bar.progress(6/total_phases)
            st.write("✅ Phase 6 complete")

            # Phase 7
            status_text.text("📘 Running Phase 7 – Figure Inline Equation (Steps 42–44)...")
            phase7_output = output_pdf_path.replace(".pdf", "_phase7.pdf")
            fp = Figure_inlineequation(pdfix)
            fp.modify_pdf_tags(output_pdf_path, phase7_output)
            output_pdf_path = phase7_output
            progress_bar.progress(7/total_phases)
            st.write("✅ Phase 7 complete")

            # Phase 8
            status_text.text("📘 Running Phase 8 – Formula Inside Figure Delete (Steps 44–45)...")
            phase8_output = output_pdf_path.replace(".pdf", "_phase8.pdf")
            fp = formula_inside_figure_delete(pdfix)
            fp.modify_pdf_tags(output_pdf_path, phase8_output)
            output_pdf_path = phase8_output
            progress_bar.progress(8/total_phases)
            st.write("✅ Phase 8 complete")

            # Complete
            status_text.text("✅ All phases complete!")
            progress_bar.progress(1.0)
            
            st.success("🎉 Processing Complete!")
            
            # Download button
            with open(output_pdf_path, "rb") as f:
                st.download_button(
                    label="⬇️ Download Processed PDF",
                    data=f,
                    file_name=f"processed_{uploaded_pdf.name}",
                    mime="application/pdf",
                )
                
        except Exception as e:
            st.error(f"❌ Error during processing: {str(e)}")
            status_text.text("❌ Processing failed")
