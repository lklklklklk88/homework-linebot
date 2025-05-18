# line_utils.py
import os
from linebot.v3.messaging import MessagingApi, ApiClient, Configuration

configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

def get_line_display_name(user_id):
    with ApiClient(configuration) as api_client:
        profile = MessagingApi(api_client).get_profile(user_id)
        return profile.display_name
