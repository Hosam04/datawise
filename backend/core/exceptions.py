class DataWiseError(Exception):
    """Base exception for all system errors."""
    pass

class FileProcessingError(DataWiseError):
    """Raised when file reading or data processing fails."""
    pass

class VisualizationError(DataWiseError):
    """Raised when chart generation fails."""
    pass

class LLMExecutionError(DataWiseError):
    """Raised when LLM invocation or output parsing fails."""
    pass

class CleaningError(DataWiseError):
    """Raised when the Cleaning Engine cannot complete safely."""
    pass