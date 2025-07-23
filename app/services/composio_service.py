from typing import List, Any, Optional
from sqlalchemy.orm import Session
from composio import Composio
from composio_langchain import LangchainProvider
from app.config import settings
from app.models.user_toolkit_connection import UserToolkitConnection, ConnectionStatus
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class ComposioService:
    def __init__(self):
        self.composio = Composio(
            api_key=settings.composio_api_key,
            provider=LangchainProvider()
        )
        self._supported_toolkits = ["GOOGLECALENDAR", "NOTION", "SLACKBOT", "GMAIL", "GOOGLETASKS", "TWITTER"]
        self.auth_configs = {
            "GOOGLECALENDAR": settings.google_calendar_auth_config_id,
            "NOTION": settings.notion_auth_config_id,
            "SLACKBOT": settings.slackbot_auth_config_id,
            "GMAIL": settings.gmail_auth_config_id,
            "GOOGLETASKS": settings.google_tasks_auth_config_id,
            "TWITTER": settings.twitter_auth_config_id,
        }
        
    def get_supported_toolkits(self) -> List[str]:
        """Get list of supported toolkit slugs."""
        return self._supported_toolkits

    def get_tools_for_user(self, user_id: str, toolkit_slugs: List[str]) -> List[Any]:
        """Get tools for a user from specified toolkits."""
        try:
            if toolkit_slugs:
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
            connections = db.query(UserToolkitConnection).filter(
                UserToolkitConnection.user_id == user_id,
                UserToolkitConnection.connection_status == ConnectionStatus.ACTIVE
            ).all()

            logger.debug(f"Enabled toolkits for user {user_id}: {[conn.toolkit_slug for conn in connections]}")
            
            return [conn.toolkit_slug for conn in connections]
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


    def set_toolkit_connection_status(self, db: Session, user_id: int, toolkit_slug: str, status: ConnectionStatus, connected_account_id: Optional[str] = None, error_message: Optional[str] = None, connection_request_id: Optional[str] = None) -> bool:
        """Set toolkit connection status for a user."""
        try:
            if not self.validate_toolkit_slug(toolkit_slug):
                logger.warning(f"Toolkit {toolkit_slug} is not supported")
                return False
            
            connection = db.query(UserToolkitConnection).filter(
                UserToolkitConnection.user_id == user_id,
                UserToolkitConnection.toolkit_slug == toolkit_slug.upper()
            ).first()
            
            if connection:
                connection.connection_status = status
                if connected_account_id is not None:
                    connection.connected_account_id = connected_account_id
                connection.error_message = error_message
                if connection_request_id is not None:
                    connection.connection_request_id = connection_request_id
                setattr(connection, 'last_synced_at', datetime.now(timezone.utc))
            else:
                connection = UserToolkitConnection(
                    user_id=user_id,
                    toolkit_slug=toolkit_slug.upper(),
                    connection_status=status,
                    connected_account_id=connected_account_id,
                    error_message=error_message,
                    connection_request_id=connection_request_id,
                    last_synced_at=datetime.now(timezone.utc)
                )
                db.add(connection)
            
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error setting toolkit connection status for user {user_id} and toolkit {toolkit_slug}: {str(e)}")
            db.rollback()
            return False

    def enable_toolkit_for_user(self, db: Session, user_id: int, toolkit_slug: str) -> bool:
        """Enable a toolkit for a user."""
        return self.set_toolkit_connection_status(db, user_id, toolkit_slug, ConnectionStatus.ACTIVE)

    def disable_toolkit_for_user(self, db: Session, user_id: int, toolkit_slug: str) -> bool:
        """Disable a toolkit for a user."""
        return self.set_toolkit_connection_status(db, user_id, toolkit_slug, ConnectionStatus.DISCONNECTED)

    def get_user_connections(self, db: Session, user_id: int) -> List[UserToolkitConnection]:
        """Get all toolkit connections for a user."""
        try:
            connections = db.query(UserToolkitConnection).filter(
                UserToolkitConnection.user_id == user_id
            ).all()
            return connections
        except Exception as e:
            logger.error(f"Error getting connections for user {user_id}: {str(e)}")
            return []

    def get_connection_status(self, db: Session, user_id: int, toolkit_slug: str) -> Optional[UserToolkitConnection]:
        """Get connection status for a specific toolkit."""
        try:
            connection = db.query(UserToolkitConnection).filter(
                UserToolkitConnection.user_id == user_id,
                UserToolkitConnection.toolkit_slug == toolkit_slug.upper()
            ).first()
            return connection
        except Exception as e:
            logger.error(f"Error getting connection status for user {user_id} and toolkit {toolkit_slug}: {str(e)}")
            return None

    
    def sync(self, db: Session, connection_request_id: str) -> bool:
        """Sync connection using connection_request_id from Composio and update database."""
        try:
            connected_account = self.composio.connected_accounts.get(connection_request_id)
            
            if not connected_account:
                logger.error(f"No connected account found for connection_request_id: {connection_request_id}")
                return False
            
            connection = db.query(UserToolkitConnection).filter(
                UserToolkitConnection.connection_request_id == connection_request_id
            ).first()
            
            if not connection:
                return False
            
            composio_status = connected_account.status.upper()
            
            if composio_status == "ACTIVE":
                self.set_toolkit_connection_status(
                    db, connection.user_id, connection.toolkit_slug, 
                    ConnectionStatus.ACTIVE, 
                    connected_account_id=connected_account.id,
                    error_message=None
                )
                print(f"Successfully synced connection for user {connection.user_id} and toolkit {connection.toolkit_slug}")
                return True
            elif composio_status in ["INITIALIZING", "INITIATED"]:
                self.set_toolkit_connection_status(
                    db, connection.user_id, connection.toolkit_slug, 
                    ConnectionStatus.PENDING,
                    connected_account_id=connected_account.id,
                    error_message=f"Connection is {composio_status.lower()}"
                )
                print(f"Connection is {composio_status.lower()} for user {connection.user_id} and toolkit {connection.toolkit_slug}")
                return True
            elif composio_status in ["FAILED", "EXPIRED", "INACTIVE"]:
                error_msg = f"Connection status in Composio is: {composio_status}"
                self.set_toolkit_connection_status(
                    db, connection.user_id, connection.toolkit_slug, 
                    ConnectionStatus.FAILED,
                    connected_account_id=connected_account.id,
                    error_message=error_msg
                )
                logger.warning(f"Connection failed for user {connection.user_id} and toolkit {connection.toolkit_slug}: {error_msg}")
                return False
            else:
                error_msg = f"Unknown connection status in Composio: {composio_status}"
                self.set_toolkit_connection_status(
                    db, connection.user_id, connection.toolkit_slug, 
                    ConnectionStatus.FAILED,
                    connected_account_id=connected_account.id,
                    error_message=error_msg
                )
                logger.warning(f"Unknown connection status for user {connection.user_id} and toolkit {connection.toolkit_slug}: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"Error syncing connection with request_id {connection_request_id}: {str(e)}")
            
            try:
                connection = db.query(UserToolkitConnection).filter(
                    UserToolkitConnection.connection_request_id == connection_request_id
                ).first()
                
                if connection:
                    self.set_toolkit_connection_status(
                        db, connection.user_id, connection.toolkit_slug, 
                        ConnectionStatus.FAILED,
                        error_message=f"Sync failed: {str(e)}"
                    )
            except Exception as db_error:
                logger.error(f"Failed to update database with error status: {str(db_error)}")
            
            return False

    def initiate_connection_with_db_update(self, db: Session, toolkit_slug: str, user_id: str):
        """Initiate OAuth connection and update database."""
        try:
            if not self.validate_toolkit_slug(toolkit_slug):
                raise ValueError(f"Toolkit {toolkit_slug} is not supported")

            connection_request = self.initiate_connection(toolkit_slug, user_id)
            
            self.set_toolkit_connection_status(
                db, int(user_id), toolkit_slug, ConnectionStatus.PENDING,
                connection_request_id=connection_request.id
            )
            
            connection = db.query(UserToolkitConnection).filter(
                UserToolkitConnection.connection_request_id == connection_request.id
            ).first()
            if connection:
                connection.auth_config_id = self.auth_configs.get(toolkit_slug.upper())
                db.commit()
            
            return connection_request
        except Exception as e:
            logger.error(f"Error initiating connection for user {user_id} and toolkit {toolkit_slug}: {str(e)}")
            raise


composio_service = ComposioService() 