# AMD Developer Cloud: Cost Management & Work Preservation

This guide explains how to protect your work and stop billing on high-cost AMD MI300X instances.

## 1. Stop Billing (Snapshot & Destroy)
**Crucial:** Powering off an instance does NOT stop billing. You must destroy the instance to stop charges.

1. **Take a Snapshot:**
   - Log in to [devcloud.amd.com](https://devcloud.amd.com/).
   - Navigate to **Instances** / **GPU Droplets**.
   - Click **Actions (...)** > **Create Snapshot**.
   - Name it: `agentic-vision-qwen-final`.
   - **Wait** for the status to become "Available" (can take 10-20 minutes).
2. **Destroy the Instance:**
   - Click **Actions (...)** > **Destroy**.
   - Billing stops immediately once the instance is deleted.

## 2. Resume Work (Restore from Snapshot)
1. **Launch New Instance:**
   - Click **Launch Instance** in the AMD portal.
   - Go to the **Snapshots** or **Custom Images** tab.
   - Select your saved snapshot.
2. **Re-activate the VLM:**
   - Once the instance is running, SSH in.
   - The Docker container will be present. Start it:
     ```bash
     docker start qwen-vllm
     ```
3. **Update Local App:**
   - Get the **New Public IP** of the instance.
   - Update your local `backend/.env` file:
     ```env
     VLM_BASE_URL=http://<NEW_IP>:8000/v1
     LLM_BASE_URL=http://<NEW_IP>:8000/v1
     ```

## 3. Fail-safe: One-Click Setup Script
If you lose your snapshot or want to start fresh on a new instance, run this script:

```bash
#!/bin/bash
# setup_vlm.sh
# One-click Qwen2.5-VL setup for AMD MI300X

# 1. Install Docker
sudo apt-get update && sudo apt-get install -y docker.io
sudo usermod -aG docker $USER

# 2. Run vLLM with Qwen2.5-VL
docker run -d --name qwen-vllm \
  --device=/dev/kfd --device=/dev/dri \
  --group-add video \
  --shm-size 16g \
  -p 8000:8000 \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  vllm/vllm-openai:latest-rocm \
  --model Qwen/Qwen2.5-VL-7B-Instruct \
  --trust-remote-code \
  --dtype bfloat16 \
  --max-model-len 4096

echo "VLM is starting. Track progress with: docker logs -f qwen-vllm"
```

## 4. Local Data Security
Your application data (SQLite database, uploaded videos, and local events) is stored **on your laptop** in the `data/` folder. It is safe and does not need to be backed up from the cloud.
