import os
from pathlib import Path

class Storage:
    def __init__(self):
        self.bucket = os.getenv('S3_BUCKET', '')
        self.root = Path(os.getenv('UPLOAD_DIR', './uploads'))
        if self.bucket:
            import boto3
            self.s3 = boto3.client('s3', region_name=os.getenv('AWS_REGION', 'us-east-2'))
        else:
            self.root.mkdir(parents=True, exist_ok=True)

    def save(self, key, photo):
        if self.bucket:
            self.s3.put_object(Bucket=self.bucket, Key=key, Body=photo, ContentType='image/jpeg', ServerSideEncryption='AES256')
        else:
            (self.root / key).write_bytes(photo)

    def read(self, key):
        if self.bucket:
            return self.s3.get_object(Bucket=self.bucket, Key=key)['Body'].read()
        return (self.root / key).read_bytes()

    def delete(self, key):
        if self.bucket:
            self.s3.delete_object(Bucket=self.bucket, Key=key)
        else:
            (self.root / key).unlink(missing_ok=True)
