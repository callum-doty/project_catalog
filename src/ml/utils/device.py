# Create utils/device.py for GPU support
import torch

def get_device():
    """Get the appropriate device for tensor operations."""
    if torch.backends.mps.is_available():
        return torch.device("mps")
    elif torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")
