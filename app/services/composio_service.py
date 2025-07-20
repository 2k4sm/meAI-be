from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from composio import Composio
from composio.types import auth_scheme
from composio_langchain import LangchainProvider
from app.config import settings
from app.models.user_tool_preference import UserToolPreference
from app.schemas.tool import ToolkitInfo
import logging

logger = logging.getLogger(__name__)


class ComposioService:
    def __init__(self):
        self.composio = Composio(
            api_key=settings.composio_api_key,
            provider=LangchainProvider()
        )
        self._supported_toolkits = ["GOOGLECALENDAR", "GOOGLETASKS", "GOOGLEDRIVE", "GMAIL"]
        self.auth_configs = {
            "GOOGLECALENDAR": settings.google_calendar_auth_config_id,
            "GOOGLETASKS": settings.google_tasks_auth_config_id,
            "GOOGLEDRIVE": settings.google_drive_auth_config_id,
            "GMAIL": settings.gmail_auth_config_id,
        }

    def get_tools_for_user(self, user_id: str, toolkit_slugs: List[str]) -> List[Any]:
        """Get tools for a user from specified toolkits."""
        try:
            valid_toolkits = []
            if toolkit_slugs != []:
            # Filter to only supported toolkits
                valid_toolkits = [slug for slug in toolkit_slugs if slug.upper() in self._supported_toolkits]
            else:
                valid_toolkits = self._supported_toolkits
            
            tools = self.composio.tools.get(user_id=user_id, toolkits=valid_toolkits)
            return tools or []
        except Exception as e:
            logger.error(f"Error fetching tools for user {user_id}: {str(e)}")
            return []

    def get_user_enabled_toolkits(self, db: Session, user_id: int) -> List[str]:
        """Get list of enabled toolkit slugs for a user."""
        try:
            preferences = db.query(UserToolPreference).filter(
                UserToolPreference.user_id == user_id,
                UserToolPreference.is_enabled == True
            ).all()

            print("toolkits", [pref.toolkit_slug for pref in preferences])
            
            return [pref.toolkit_slug for pref in preferences]
        except Exception as e:
            logger.error(f"Error getting enabled toolkits for user {user_id}: {str(e)}")
            return []

    def validate_toolkit_slug(self, toolkit_slug: str) -> bool:
        """Validate if a toolkit slug is supported."""
        return toolkit_slug.upper() in self._supported_toolkits

    def initiate_connection(self, toolkit_slug: str, user_id: str, redirect_url: Optional[str] = None):
        """Initiate OAuth connection for a toolkit."""
        auth_config_id = self.auth_configs.get(toolkit_slug.upper())
        if not auth_config_id:
            raise ValueError(f"No auth config found for toolkit {toolkit_slug}")
        
        return self.composio.connected_accounts.initiate(
            user_id=user_id,
            auth_config_id=auth_config_id,
            callback_url=redirect_url
        )

    def wait_for_connection(self, connection_request_id: str):
        """Wait for connection to be established."""
        return self.composio.connected_accounts.wait_for_connection(connection_request_id)
    
    def get_connected_account(self, connection_request_id: str):
        """Get connected account by connection request id."""
        return self.composio.connected_accounts.get(connection_request_id)

    def set_toolkit_preference(self, db: Session, user_id: int, toolkit_slug: str, enabled: bool) -> bool:
        """Set toolkit preference (enable/disable) for a user."""
        try:
            # Check if toolkit is supported
            if not self.validate_toolkit_slug(toolkit_slug):
                logger.warning(f"Toolkit {toolkit_slug} is not supported")
                return False
            
            # Find existing preference or create new one
            preference = db.query(UserToolPreference).filter(
                UserToolPreference.user_id == user_id,
                UserToolPreference.toolkit_slug == toolkit_slug.upper()
            ).first()
            
            if preference:
                preference.is_enabled = enabled
            else:
                preference = UserToolPreference(
                    user_id=user_id,
                    toolkit_slug=toolkit_slug.upper(),
                    is_enabled=enabled
                )
                db.add(preference)
            
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error setting toolkit preference for user {user_id} and toolkit {toolkit_slug}: {str(e)}")
            db.rollback()
            return False

    def enable_toolkit_for_user(self, db: Session, user_id: int, toolkit_slug: str) -> bool:
        """Enable a toolkit for a user."""
        return self.set_toolkit_preference(db, user_id, toolkit_slug, True)

    def disable_toolkit_for_user(self, db: Session, user_id: int, toolkit_slug: str) -> bool:
        """Disable a toolkit for a user."""
        return self.set_toolkit_preference(db, user_id, toolkit_slug, False)


# Global instance
composio_service = ComposioService() 