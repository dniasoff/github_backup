# S3 Bucket for backup storage
resource "aws_s3_bucket" "backup_bucket" {
  bucket = var.s3_bucket_name
}

resource "aws_s3_bucket_versioning" "backup_bucket_versioning" {
  bucket = aws_s3_bucket.backup_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Enable S3 Intelligent Tiering for automatic cost optimization
resource "aws_s3_bucket_intelligent_tiering_configuration" "backup_bucket_intelligent_tiering" {
  bucket = aws_s3_bucket.backup_bucket.id
  name   = "backup-intelligent-tiering"

  # Apply to all objects - omit filter block entirely for all objects

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 90
  }

  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = 180
  }

  # Optional: Enable tiering for small objects (extra cost but better optimization)
  # optional_fields = ["BucketKeyStatus"]  # Not supported in current provider version
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backup_bucket_encryption" {
  bucket = aws_s3_bucket.backup_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backup_bucket_lifecycle" {
  bucket = aws_s3_bucket.backup_bucket.id

  rule {
    id     = "nightly_backup_retention"
    status = "Enabled"

    # Transition to Glacier IR after 7 days (cheaper storage for backups)
    transition {
      days          = 7
      storage_class = "GLACIER_IR"
    }

    # Simple expiration after 30 days for nightly backups
    expiration {
      days = var.retention_days  # 30 days
    }

    # Clean up versions after 7 days to save costs
    noncurrent_version_expiration {
      noncurrent_days = 7
    }

    # Clean up incomplete multipart uploads
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }

    filter {
      prefix = "nightly/"
    }
  }

  rule {
    id     = "final_backup_preservation"
    status = "Enabled"

    # Final backups (when repo is deleted) - keep forever but move to cheap storage
    transition {
      days          = 30  # Move to Standard-IA after 30 days
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90  # Move to Glacier IR after 90 days
      storage_class = "GLACIER_IR"
    }

    transition {
      days          = 365  # Move to Deep Archive after 1 year
      storage_class = "DEEP_ARCHIVE"
    }

    # No expiration - keep forever
    # expiration { } # Commented out to keep forever

    # Clean up versions to save costs
    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    filter {
      prefix = "final/"
    }
  }

  rule {
    id     = "cleanup_orphaned_objects"
    status = "Enabled"

    # Clean up delete markers
    expiration {
      expired_object_delete_marker = true
    }

    # Clean up incomplete uploads
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }

    filter {}
  }
}

resource "aws_s3_bucket_public_access_block" "backup_bucket_pab" {
  bucket = aws_s3_bucket.backup_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}