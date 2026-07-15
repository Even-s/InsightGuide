#!/usr/bin/env bash
set -Eeuo pipefail

INSTANCE_ID=${INSTANCE_ID:?Set INSTANCE_ID to the target EC2 instance ID}
AWS_PROFILE=${AWS_PROFILE:-default}
AWS_REGION=${AWS_REGION:-ap-northeast-1}

pids=()

cleanup() {
  for pid in "${pids[@]:-}"; do
    kill "${pid}" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

start_tunnel() {
  local remote_port=$1
  local local_port=$2
  aws ssm start-session \
    --target "${INSTANCE_ID}" \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}" \
    --document-name AWS-StartPortForwardingSession \
    --parameters "portNumber=${remote_port},localPortNumber=${local_port}" &
  pids+=("$!")
}

start_tunnel 8080 5174
start_tunnel 9000 9000

echo "InsightGuide SSM tunnels are starting:"
echo "  App:   http://localhost:5174"
echo "  Files: http://localhost:9000"
echo "Keep this terminal open. Press Ctrl+C to stop both tunnels."

wait
