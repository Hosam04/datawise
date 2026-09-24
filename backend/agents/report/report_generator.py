from backend.agents.base.base_agent import BaseAgent
from backend.core.state import AgentState
from backend.tools.exporter import PDFExporter
import os

class ReportGeneratorAgent(BaseAgent):
    def __init__(self):
        super().__init__("ReportGeneratorAgent")

    def run(self, state: AgentState) -> AgentState:
        self.log_execution(state.session_id)

        try:
            original_filename = os.path.basename(state.file_path)

            dataset_name = os.path.splitext(original_filename)[0]

            report_filename = f"{dataset_name}_report.pdf"

            output_pdf_path = os.path.join(state.session_dir, report_filename)

            # Use the tool to generate the report
            PDFExporter.generate_report(
                output_path=output_pdf_path,
                content=state.final_report,
                image_paths=state.visualization_paths,
                title=f"{dataset_name} - Data Analysis Report"  
            )

            state.final_report_path = output_pdf_path
            self.logger.info("PDF Report generated successfully at: %s", output_pdf_path)

            return state

        except Exception as e:
            self.logger.error("Failed to generate PDF report: %s", str(e))
            raise e