"""S3 storage service for file operations."""

import logging
from typing import BinaryIO, Optional
from io import BytesIO

import boto3
from botocore.exceptions import ClientError
from botocore.client import Config

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Service:
    """Service for interacting with S3-compatible object storage."""

    def __init__(self):
        """Initialize S3 client."""
        self.bucket_name = settings.S3_BUCKET_NAME
        self.presigned_endpoint = settings.s3_presigned_endpoint_url
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
            config=Config(signature_version="s3v4"),
        )
        self.presign_client = boto3.client(
            "s3",
            endpoint_url=self.presigned_endpoint,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
            config=Config(signature_version="s3v4"),
        )
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        """Ensure the configured bucket exists, create if not."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket {self.bucket_name} exists")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                try:
                    self.client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Created bucket {self.bucket_name}")
                except ClientError as create_error:
                    logger.warning(f"Failed to create bucket (MinIO may be unavailable): {create_error}")
                    # Don't raise - allow app to start even if MinIO is down
            else:
                logger.warning(f"Error checking bucket (MinIO may be unavailable): {e}")
                # Don't raise - allow app to start even if MinIO is down
        except Exception as e:
            logger.warning(f"Could not connect to MinIO: {e}")
            # Don't raise - allow app to start even if MinIO is down

    def upload_file(
        self,
        file_obj: BinaryIO,
        object_key: str,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Upload a file to S3.

        Args:
            file_obj: File-like object to upload
            object_key: Key (path) for the object in S3
            content_type: MIME type of the file

        Returns:
            URL of the uploaded file
        """
        try:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type

            self.client.upload_fileobj(
                file_obj,
                self.bucket_name,
                object_key,
                ExtraArgs=extra_args,
            )

            url = f"{settings.S3_ENDPOINT_URL}/{self.bucket_name}/{object_key}"
            logger.info(f"Uploaded file to {url}")
            return url

        except ClientError as e:
            logger.error(f"Failed to upload file {object_key}: {e}")
            raise

    def download_file(self, object_key: str) -> BytesIO:
        """
        Download a file from S3.

        Args:
            object_key: Key (path) of the object in S3

        Returns:
            BytesIO object containing the file data
        """
        try:
            file_obj = BytesIO()
            self.client.download_fileobj(self.bucket_name, object_key, file_obj)
            file_obj.seek(0)
            logger.info(f"Downloaded file {object_key}")
            return file_obj

        except ClientError as e:
            logger.error(f"Failed to download file {object_key}: {e}")
            raise

    def delete_file(self, object_key: str) -> None:
        """
        Delete a file from S3.

        Args:
            object_key: Key (path) of the object to delete
        """
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_key)
            logger.info(f"Deleted file {object_key}")

        except ClientError as e:
            logger.error(f"Failed to delete file {object_key}: {e}")
            raise

    def generate_presigned_url(
        self,
        file_url: str,
        expiration: int = 3600
    ) -> str:
        """
        Generate a presigned URL for temporary access to a file.

        Args:
            file_url: The full S3 URL of the file
            expiration: Time in seconds for the URL to remain valid

        Returns:
            Presigned URL for accessing the file
        """
        try:
            # Extract object key from URL
            object_key = file_url.split(f"{self.bucket_name}/")[-1]

            presigned_url = self.presign_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": object_key
                },
                ExpiresIn=expiration
            )

            logger.info(f"Generated presigned URL for {object_key}")
            return presigned_url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise


# Global S3 service instance
s3_service = S3Service()
