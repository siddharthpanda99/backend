import logging
from typing import Dict, Any, Optional

from common_lib.modules.integration import get_integration

logger = logging.getLogger(__name__)

class ExtAppEngine:
    def __init__(self):
        self.integration = get_integration()
        self.bridge = self.integration.get("cross_module_bridge")

    async def handle_view_event(
        self,
        event_type: str,
        view_id: str,
        user_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process an event from an Ext-App view (e.g. tools/call, ui/message)
        and route it through the cross-module bridge.
        """
        logger.info(f"Processing Ext-App event {event_type} for view {view_id}")
        
        # Format the event for the bridge
        bridge_event = f"ext_app.{event_type.replace('/', '_')}"
        
        payload = {
            "view_id": view_id,
            "user_id": user_id,
            "raw_data": data
        }

        if self.bridge:
            result = await self.bridge.process_event(
                event_type=bridge_event,
                data=payload,
                channel="ext_apps"
            )
            return {"status": "processed", "bridge_results": result}
        else:
            logger.warning("Cross-module bridge not available, skipping event routing")
            return {"status": "unprocessed", "reason": "bridge_unavailable"}

def get_ext_app_engine() -> ExtAppEngine:
    return ExtAppEngine()
