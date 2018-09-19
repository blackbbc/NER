from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import random

import numpy as np
import bottleneck as bn

from utils.conlleval import evaluate_conll_file



def conll_format(token, la_true, la_pred, idx2w, idx2la, prefix):
    with open('dev/%s.predict_conll' % prefix, 'w') as fp:
        for sw, se, sl in zip(token, la_true, la_pred):
            for a, b, c in zip(sw, se, sl):
                fp.write(idx2w[a] + ' ' + idx2la[b] + ' ' + idx2la[c] + '\n')
            fp.write('\n')

    with open('dev/%s.predict_conll' % prefix, 'r') as fp:
        (prec, rec, f1) = evaluate_conll_file(fp)

    with open('eval/%s.detail' % prefix, 'w') as fp:
        fp.write('Precision: %f, Recall: %f, F1: %f\n' % (prec, rec, f1))

    return f1


def viterbi_decode_topk(score, transition_params, topK = 1):
    """Decode the top K scoring sequence of tags outside of TensorFlow.

    This should only be used at test time.

    Args:
        score: A [seq_len, num_tags] matrix of unary potentials.
        transition_params: A [num_tags, num_tags] matrix of binary potentials.
        k: Top K

    Returns:
        viterbi: A [seq_len] list of integers containing the highest scoring tag
          indices.
        viterbi_score: A float containing the score for the Viterbi sequence.
    """

    seq_len, num_tags = score.shape

    trellis = np.zeros((topK, seq_len, num_tags))
    backpointers = np.zeros_like(trellis, dtype=np.int32)
    trellis[0, 0] = score[0]
    trellis[1:topK, 0] = -1e16 # Mask

    # Compute score
    for t in range(1, seq_len):
        v = np.zeros((num_tags * topK, num_tags))
        for k in range(topK):
            tmp = np.expand_dims(trellis[k, t - 1], 1) + transition_params
            v[k * num_tags: (k + 1) * num_tags, :] = tmp

        args = np.argsort(-v, 0) # Desc
        for k in range(topK):
            trellis[k, t] = score[t] + v[args[k, :], np.arange(num_tags)]
            backpointers[k, t] = args[k, :]

    # Decode topK
    v = trellis[:, -1, :] # [topK, num_tags]
    v = v.flatten()

    args = np.argsort(-v)[:topK]
    scores = v[args]

    sequences = []
    for k in range(topK):
        viterbi = [args[k]]

        for t in range(seq_len - 1, 0, -1):
            last = viterbi[-1]
            id1 = last // num_tags
            id2 = last % num_tags
            viterbi.append(backpointers[id1, t, id2])

        viterbi.reverse()
        viterbi = [x % num_tags for x in viterbi]
        sequences.append(viterbi)

    return sequences, scores


def viterbi_decode(score, transition_params):
    """Decode the highest scoring sequence of tags outside of TensorFlow.
    This should only be used at test time.
    Args:
      score: A [seq_len, num_tags] matrix of unary potentials.
      transition_params: A [num_tags, num_tags] matrix of binary potentials.
    Returns:
      viterbi: A [seq_len] list of integers containing the highest scoring tag
          indices.
      viterbi_score: A float containing the score for the Viterbi sequence.
    """
    trellis = np.zeros_like(score)
    backpointers = np.zeros_like(score, dtype=np.int32)
    trellis[0] = score[0]

    for t in range(1, score.shape[0]):
        v = np.expand_dims(trellis[t - 1], 1) + transition_params
        trellis[t] = score[t] + np.max(v, 0)
        backpointers[t] = np.argmax(v, 0)

    viterbi = [np.argmax(trellis[-1])]
    for bp in reversed(backpointers[1:]):
        viterbi.append(bp[viterbi[-1]])
    viterbi.reverse()

    viterbi_score = np.max(trellis[-1])
    return viterbi, viterbi_score