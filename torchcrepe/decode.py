import librosa
import numpy as np
import torch

import torchcrepe


###############################################################################
# Probability sequence decoding methods
###############################################################################


def argmax(logits):
    """Sample observations by taking the argmax"""
    bins = logits.argmax(dim=1)

    # Convert to frequency in Hz
    return bins, torchcrepe.convert.bins_to_frequency(bins)


def weighted_argmax(logits):
    """Sample observations using weighted sum near the argmax"""
    # Find center of analysis window
    bins = logits.argmax(dim=1)

    # Find bounds of analysis window
    start = torch.max(torch.tensor(0, device=logits.device), bins - 4)
    end = torch.min(torch.tensor(360, device=logits.device), bins + 5)

    # Mask out everything outside of window
    for batch in range(logits.size(0)):
        for time in range(logits.size(2)):
            logits[batch, :start[batch, time], time] = 0.0
            logits[batch, end[batch, time]:, time] = 0.0

    # Construct weights
    if not hasattr(weighted_argmax, 'weights'):
        weights = torchcrepe.convert.bins_to_cents(torch.arange(360))
        weighted_argmax.weights = weights[None, :, None]

    # Ensure devices are the same (no-op if they are)
    weighted_argmax.weights = weighted_argmax.weights.to(logits.device)

    # Apply weights
    cents = (weighted_argmax.weights * logits).sum(dim=1) / logits.sum(dim=1)

    # Convert to frequency in Hz
    return bins, torchcrepe.convert.cents_to_frequency(cents)


def viterbi(logits):
    """Sample observations using viterbi decoding"""
    # Create viterbi transition matrix
    if not hasattr(viterbi, 'transition'):
        xx, yy = np.meshgrid(range(360), range(360))
        transition = np.maximum(12 - abs(xx - yy), 0)
        transition = transition / transition.sum(axis=1, keepdims=True)
        viterbi.transition = transition

    # Convert to numpy
    sequences = logits.cpu().numpy()

    # Perform viterbi decoding
    bins = np.array([librosa.sequence.viterbi(sequence, viterbi.transition)
                     for sequence in sequences], dtype='int32')

    # Convert to pytorch
    bins = torch.tensor(bins, device=logits.device)

    # Convert to frequency in Hz
    return bins, torchcrepe.convert.bins_to_frequency(bins)
