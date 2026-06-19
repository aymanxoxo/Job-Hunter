"""JobHunter core.connectors package."""
from core.connectors.base_connector import BaseConnector
from core.connectors.mock_connector import MockConnector

__all__ = ["BaseConnector", "MockConnector"]
