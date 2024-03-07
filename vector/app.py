import glob
import json
import os
import os.path
import tempfile

import boto3
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex


def get_secrets() -> dict[str, str]:
    client = boto3.client("secretsmanager")
    secretARN = os.environ["SECRET_ARN"]
    secrets = client.get_secret_value(SecretId=secretARN)
    decoded = json.loads(secrets["SecretString"])
    return decoded


secrets = get_secrets()
s3_client = boto3.client("s3")
vector_bucket = os.environ["VECTOR_BUCKET"]


def lambda_handler(event, context):
    print(f"{event=}")
    print(f"{context=}")
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = os.path.join(tmp_dir, "data")
            persist_dir = os.path.join(tmp_dir, "storage")
            os.makedirs(data_dir)
            os.makedirs(persist_dir)
            download_pdf(bucket, key, data_dir)
            vectorize(data_dir, persist_dir)
            upload_vector(vector_bucket, persist_dir)

    return {"statusCode": 200, "body": json.dumps({"message": "ok"})}


def download_pdf(bucket: str, key: str, directory: str) -> None:
    resp = s3_client.get_object(Bucket=bucket, Key=key)
    path = os.path.join(directory, key)
    with open(path, "wb") as f:
        f.write(resp["Body"].read())


def vectorize(data_dir: str, persist_dir: str) -> None:
    documents = SimpleDirectoryReader(data_dir).load_data()
    index = VectorStoreIndex.from_documents(documents)
    index.storage_context.persist(persist_dir=persist_dir)


def upload_vector(bucket: str, persist_dir: str):
    files = glob.glob(os.path.join(persist_dir, "*.json"))
    for file in files:
        key = os.path.basename(file)
        with open(file, "rb") as f:
            s3_client.put_object(Bucket=bucket, Key=key, Body=f)
