import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def save_spam_message(sender_full_name: str, message_text: str):
    spam_data = {
        "timestamp": datetime.now().isoformat(),
        "sender": sender_full_name,
        "message": message_text
    }

    try:
        with open('spam_log.json', 'a') as f:
            json.dump(spam_data, f, ensure_ascii=False)
            f.write('\n')
        logger.info("Spam logged successfully")
        logger.info(f"Spam saved. \nsender_full_name={sender_full_name}, \nmessage_text={message_text}")
    except Exception as e:
        logger.error(f"Logging failed: {e}")