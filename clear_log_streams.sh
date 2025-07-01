#!/bin/bash

# Set AWS profile
export AWS_PROFILE=vault

# Define log groups
LOG_GROUPS=(
    "/aws/lambda/github-backup-discovery"
    "/aws/lambda/github-backup-nightly"
    "/aws/lambda/github-backup-archival"
    "/aws/lambda/github-backup-glacier-cleanup"
    "/aws/lambda/github-backup-api"
    "/aws/lambda/github-backup-auth"
    "/aws/lambda/github-backup-email-formatter"
)

# Function to delete log streams for a log group
delete_log_streams() {
    local log_group=$1
    echo "Processing log group: $log_group"
    
    # Get all log streams
    log_streams=$(aws logs describe-log-streams --log-group-name "$log_group" --query 'logStreams[*].logStreamName' --output json 2>/dev/null)
    
    if [ $? -ne 0 ]; then
        echo "  Log group not found or error accessing: $log_group"
        return
    fi
    
    # Check if there are any log streams
    stream_count=$(echo "$log_streams" | jq 'length')
    
    if [ "$stream_count" -eq 0 ]; then
        echo "  No log streams found in $log_group"
        return
    fi
    
    echo "  Found $stream_count log streams to delete"
    
    # Delete each log stream
    echo "$log_streams" | jq -r '.[]' | while read -r stream_name; do
        if [ -n "$stream_name" ]; then
            echo -n "  Deleting: $stream_name ... "
            aws logs delete-log-stream --log-group-name "$log_group" --log-stream-name "$stream_name" 2>/dev/null
            if [ $? -eq 0 ]; then
                echo "✓"
            else
                echo "✗ (failed)"
            fi
        fi
    done
    
    echo "  Completed processing $log_group"
    echo ""
}

# Main execution
echo "Starting CloudWatch log stream cleanup..."
echo "========================================="
echo ""

for log_group in "${LOG_GROUPS[@]}"; do
    delete_log_streams "$log_group"
done

echo "========================================="
echo "CloudWatch log stream cleanup completed!"