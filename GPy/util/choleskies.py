# Copyright James Hensman and Max Zwiessele 2014
# Licensed under the GNU GPL version 3.0

import numpy as np
from . import linalg
from .config import config

try:
    from scipy import weave
except ImportError:
    config.set('weave', 'working', 'False')

def safe_root(N):
    i = np.sqrt(N)
    j = int(i)
    if i != j:
        raise ValueError("N is not square!")
    return j

def _flat_to_triang_weave(flat):
    """take a matrix N x D and return a M X M x D array where

    N = M(M+1)/2

    the lower triangluar portion of the d'th slice of the result is filled by the d'th column of flat.
    This is the weave implementation
    """
    N, D = flat.shape
    M = (-1 + safe_root(8*N+1))/2
    ret = np.zeros((M, M, D))
    flat = np.ascontiguousarray(flat)

    code = """
    int count = 0;
    for(int m=0; m<M; m++)
    {
      for(int mm=0; mm<=m; mm++)
      {
        for(int d=0; d<D; d++)
        {
          ret[d + m*D*M + mm*D] = flat[count];
          count++;
        }
      }
    }
    """
    weave.inline(code, ['flat', 'ret', 'D', 'M'])
    return ret

def _flat_to_triang_pure(flat_mat):
    N, D = flat_mat.shape
    M = (-1 + safe_root(8*N+1))//2
    ret = np.zeros((M, M, D))
    count = 0
    for m in range(M):
        for mm in range(m+1):
            for d in range(D):
              ret.flat[d + m*D*M + mm*D] = flat_mat.flat[count];
              count = count+1
    return ret

if config.getboolean('weave', 'working'):
	flat_to_triang =  _flat_to_triang_weave
else:
        flat_to_triang =  _flat_to_triang_pure

def _triang_to_flat_weave(L):
    M, _, D = L.shape

    L = np.ascontiguousarray(L) # should do nothing if L was created by flat_to_triang

    N = M*(M+1)/2
    flat = np.empty((N, D))
    code = """
    int count = 0;
    for(int m=0; m<M; m++)
    {
      for(int mm=0; mm<=m; mm++)
      {
        for(int d=0; d<D; d++)
        {
          flat[count] = L[d + m*D*M + mm*D];
          count++;
        }
      }
    }
    """
    weave.inline(code, ['flat', 'L', 'D', 'M'])
    return flat

def _triang_to_flat_pure(L):
    M, _, D = L.shape

    N = M*(M+1)//2
    flat = np.empty((N, D))
    count = 0;
    for m in range(M):
        for mm in range(m+1):
            for d in range(D):
                flat.flat[count] = L.flat[d + m*D*M + mm*D];
                count = count +1
    return flat

if config.getboolean('weave', 'working'):
    triang_to_flat =  _triang_to_flat_weave
else:
    triang_to_flat =  _triang_to_flat_pure

def triang_to_cov(L):
    return np.dstack([np.dot(L[:,:,i], L[:,:,i].T) for i in range(L.shape[-1])])

def multiple_dpotri_old(Ls):
    M, _, D = Ls.shape
    Kis = np.rollaxis(Ls, -1).copy()
    [dpotri(Kis[i,:,:], overwrite_c=1, lower=1) for i in range(D)]
    code = """
    for(int d=0; d<D; d++)
    {
      for(int m=0; m<M; m++)
      {
        for(int mm=0; mm<m; mm++)
        {
          Kis[d*M*M + mm*M + m ] = Kis[d*M*M + m*M + mm];
        }
      }
    }

    """
    weave.inline(code, ['Kis', 'D', 'M'])
    Kis = np.rollaxis(Kis, 0, 3) #wtf rollaxis?
    return Kis

def multiple_dpotri(Ls):
    return np.dstack([linalg.dpotri(np.asfortranarray(Ls[:,:,i]), lower=1)[0] for i in range(Ls.shape[-1])])

def indexes_to_fix_for_low_rank(rank, size):
    """
    work out which indexes of the flatteneed array should be fixed if we want the cholesky to represent a low rank matrix
    """
    #first we'll work out what to keep, and the do the set difference.

    #here are the indexes of the first column, which are the triangular numbers
    n = np.arange(size)
    triangulars = (n**2 + n) / 2
    keep = []
    for i in range(rank):
        keep.append(triangulars[i:] + i)
    #add the diagonal
    keep.append(triangulars[1:]-1)
    keep.append((size**2 + size)/2 -1)# the very last element
    keep = np.hstack(keep)

    return np.setdiff1d(np.arange((size**2+size)/2), keep)



#class cholchecker(GPy.core.Model):
    #def __init__(self, L, name='cholchecker'):
        #super(cholchecker, self).__init__(name)
        #self.L = GPy.core.Param('L',L)
        #self.link_parameter(self.L)
    #def parameters_changed(self):
        #LL = flat_to_triang(self.L)
        #Ki = multiple_dpotri(LL)
        #self.L.gradient = 2*np.einsum('ijk,jlk->ilk', Ki, LL)
        #self._loglik = np.sum([np.sum(np.log(np.abs(np.diag()))) for i in range(self.L.shape[-1])])
#
