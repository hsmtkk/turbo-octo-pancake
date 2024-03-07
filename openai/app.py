import json
import os

import boto3
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.models.events import Event
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# LINE Bot SDK Documents
# https://line-bot-sdk-python.readthedocs.io/en/stable/
# https://github.com/line/line-bot-sdk-python/tree/master


def get_secrets() -> dict[str, str]:
    client = boto3.client("secretsmanager")
    secretARN = os.environ["SECRET_ARN"]
    secrets = client.get_secret_value(SecretId=secretARN)
    decoded = json.loads(secrets["SecretString"])
    return decoded


secrets = get_secrets()
config = Configuration(access_token=secrets["channel-access-token"])
handler = WebhookHandler(channel_secret=secrets["channel-secret"])


def lambda_handler(event, context):

    @handler.add(MessageEvent, message=TextMessageContent)
    def handle_message(event: Event):
        with ApiClient(config) as api_client:
            line_bot_api = MessagingApi(api_client)
            reply_msg_req = ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=event.message.text)],
            )
            line_bot_api.reply_message_with_http_info(reply_msg_req)

    print(f"{event=}")
    print(f"{context=}")
    body = event["body"]
    signature = event["headers"]["x-line-signature"]
    print(f"{body=}")  # debug
    print(f"{signature=}")  # debug
    handler.handle(body, signature)

    return {"statusCode": 200, "body": json.dumps({"message": "ok"})}
