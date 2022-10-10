import numpy as np
from copy import deepcopy
from typing import Dict, List, Tuple, Union
import warnings
warnings.simplefilter('always', UserWarning)

from openfermion import (
    MajoranaOperator,
    FermionOperator, 
    count_qubits, 
    get_majorana_operator,
)


def convert_openF_fermionic_op_to_maj_op(fermionic_op: FermionOperator,
                                         phase_factors_included:bool=True,) -> "MajoranaOp":
    """
    Function wraps inbuilt functions in OpenFermion and returns symred form.

    Convserion as:
        a_{p} = 0.5*(γ_{2p} + iγ_{2p+1})
        a†_{p} = 0.5*(γ_{2p} - iγ_{2p+1})
     note goes from N to 2N sites!

    Args:
        fermionic_op (FermionOperator): openfermion FermionOperator
    Returns:
        op_out (MajoranaOp): majorana form of input fermionic_op

    """
    if not isinstance(fermionic_op, FermionOperator):
        raise ValueError('not an openfermion Fermionic operator')

    N_sites = count_qubits(fermionic_op)
    maj_operator = get_majorana_operator(fermionic_op)

    N_terms = len(maj_operator.terms)
    majorana = np.zeros((N_terms, 2 * N_sites))
    coeffs = np.zeros(N_terms, dtype=complex)
    for ind, term_coeff in enumerate(maj_operator.terms.items()):
        majorana[ind, term_coeff[0]] = 1
        coeffs[ind] = term_coeff[1]

    op_out = MajoranaOp(majorana, coeffs, phase_factors_included=phase_factors_included).cleanup()

    #     if op_out.to_OF_op() != get_majorana_operator(fermionic_op):
    #         # check using openF == comparison
    #         raise ValueError('op not converted correctly')

    return op_out


def bubble_sort_maj(array):
    """

    Given an array/list of majorana modes use bubble sort alg to reorder by size and keep track of sign

    e.g. given
    [12,10] then we get y_10 y_12 (but order change here must generate a negative sign!)
     y_12 y_10 ==  -1*(y_10 y_12)

    Args:
        array (list): list of ints

    Returns:
        arr (list): sorted list of ints
        sign (int): +1 or -1 sign generated by normal ordering

    """

    arr = np.asarray(array)
    n_sites = arr.shape[0]
    sign_dict = {0: +1, 1:-1}
    # Traverse through all array elements
    swap_counter = 0
    for i in range(n_sites):
        swapped = False
        for j in range(0, n_sites - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
                swap_counter+=1

        if swapped == False:
            break

    return arr.tolist(), sign_dict[swap_counter%2]


class MajoranaOp:
    """
    A class thats represents an operator defined as Majorana fermionic operators (stored in a symplectic representation).

    Note Majorana operators follow the following definition:

    { γ_{j} , γ_{k} } = 2δ_{jk}I (aka same as the Pauli group!)

    """

    def __init__(self,
                 list_lists_OR_sympletic_form: Union[List[int], np.array],
                 coeff_list: np.array,
                 phase_factors_included:bool=False,
                 ) -> None:
        """
        TODO: need to fix ordering in init! ( aka if one defines [[12,10]] then we get y_10 y_12 (but order change here must change sign!)
        """
        self.phase_factors_included = phase_factors_included
        self.coeff_vec = np.asarray(coeff_list, dtype=complex)
        self.initalize_op(list_lists_OR_sympletic_form)
        self.term_index_list = np.arange(0, self.n_sites, 1)
        self.n_terms = self.symp_matrix.shape[0]

        # 2i positions
        self.even_inds = np.arange(0,self.n_sites, 2)
        # 2i+1 positions
        self.odd_inds = np.arange(1,self.n_sites, 2)

    def initalize_op(self, input_term: Union[List[int], np.array]):
        """
        Each row in symplectic array is defined as:
        𝛾𝐴= 𝑖^{⌊|𝛾𝐴|2⌋} * ∏_{𝑘∈𝐴} 𝛾𝑘

        where 𝑖^{⌊|𝛾𝐴|2⌋} gives phase factor which ensures these operators are Hermitian!

        See eq 10 of: https://arxiv.org/pdf/2102.00620.pdf

        Args:
            input_term:
            calc_phase (bool): whether to calculate phase factors (NOTE SHOULD NOT DO THIS WHEN ADDING AND MULTIPLYING)

        Returns:

        """
        if isinstance(input_term, np.ndarray):
            if (len(input_term)==0) and (len(self.coeff_vec)==1):
                self.n_sites = 2
                self.symp_matrix = np.array([[0,0]], dtype=int)
            else:
                if len(input_term.shape)==1:
                    input_term = input_term.reshape([1,-1])

                self.n_sites = input_term.shape[1]
                assert(self.n_sites%2==0), 'not even moded'
                self.symp_matrix = input_term.astype(int)
        else:
            flat_list = set(item for sublist in input_term for item in sublist)
            if flat_list:
                n_sites = max(flat_list) + 1
                if n_sites%2!=0:
                    n_sites+=1
                self.n_sites = n_sites
            else:
                self.n_sites = 2
            n_terms = len(input_term)
            self.symp_matrix = np.zeros((n_terms, self.n_sites), dtype=int)
            for ind, term in enumerate(input_term):
                ordered_term, sign = bubble_sort_maj(term)
                self.symp_matrix[ind, ordered_term] = 1
                self.coeff_vec[ind] *= sign

        assert (self.symp_matrix.shape[0] == len(self.coeff_vec)), 'incorrect number of coefficients'

        ## calc phase factors
        if self.phase_factors_included is False:
            # calculate phase factors and update coeff vector
            self.coeff_vec*= (1j)**(np.einsum('ij->i', self.symp_matrix)//2)

    def __str__(self) -> str:
        """
        Defines the print behaviour of MajoranaOp -
        returns the operator in an easily readable format

        Returns:
            out_string (str): human-readable MajoranaOp string
        """
        out_string = ''
        for majorana_vec, ceoff in zip(self.symp_matrix, self.coeff_vec):
            maj_inds = self.term_index_list[majorana_vec.astype(bool)]
            maj_string = ' '.join([f'γ{ind}' for ind in maj_inds])
            if maj_string == '':
                maj_string = 'I'

            out_string += (f'{ceoff} {maj_string} +\n')
        return out_string[:-3]

    def commutator(self, M_OP: "MajoranaOp") -> "MajoranaOp":
        """ Computes the commutator [A, B] = AB - BA
        """
        return (self * M_OP - M_OP * self).cleanup()

    def anticommutator(self, M_OP: "MajoranaOp") -> "MajoranaOp":
        """ Computes the anticommutator {A, B} = AB + BA
        """
        return (self * M_OP + M_OP * self).cleanup()

    def commutes(self,
            M_OP: "MajoranaOp"
        ) -> bool:
        """ Checks if every term of self commutes with every term of Pword
        """
        return self.commutator(M_OP).n_terms == 0

    @property
    def dagger(self) -> "MajoranaOp":
        """
        Similar idea to hermitian conjugate operation on Fermionic operators (reverse order then dagger)
        As operators are self dagger, just reverse order!

        Returns:
            Maj_conj (MajoranaOp): The Hermitian conjugated operator
        """
        new_terms = []
        for sym_vec in self.symp_matrix:
            current_term = self.term_index_list[sym_vec.astype(bool)]
            new_terms.append(current_term[::-1]) # reverse order
        Maj_conj = MajoranaOp(new_terms, self.coeff_vec.conjugate(), phase_factors_included=True)
        return Maj_conj

    def commutes_termwise(self, M_OP: "MajoranaOp") -> np.array:
        """ Computes commutation relations between self and another MajoranaOp

        see https://arxiv.org/pdf/2101.09349.pdf (eq 9)
        """
        if self.n_sites != M_OP.n_sites:
            sites = min(self.n_sites, M_OP.n_sites)
        else:
            sites = self.n_sites

        suppA = np.einsum('ij->i', self.symp_matrix)
        suppB = np.einsum('ij->i', M_OP.symp_matrix)
        AtimeB = np.outer(suppA, suppB) # need all combinations of suppA times suppB

        # only look over common inds
        AandB = np.dot(self.symp_matrix[:, :sites], M_OP.symp_matrix[:, :sites].T)
        comm_flag = (AtimeB + AandB + 1) % 2

        return comm_flag

    def adjacency_matrix(self):
        """ Checks which terms of self commute within itself
        """
        adj = self.commutes_termwise(self)
        return adj

    def copy(self) -> "MajoranaOp":
        """
        Create a carbon copy of the class instance
        """
        return deepcopy(self)

    def __add__(self,
                M_OP: "MajoranaOp"
                ) -> "MajoranaOp":
        """ Add to this PauliwordOp another PauliwordOp by stacking the
        respective symplectic matrices and cleaning any resulting duplicates
        """
        if self.n_sites != M_OP.n_sites:
            if self.n_sites < M_OP.n_sites:
                temp_mat = np.zeros((self.n_terms, M_OP.n_sites))
                temp_mat[:, :self.n_sites] += self.symp_matrix
                P_symp_mat_new = np.vstack((temp_mat, M_OP.symp_matrix))
            else:
                temp_mat = np.zeros((M_OP.n_terms, self.n_sites))
                temp_mat[:, :M_OP.n_sites] += M_OP.symp_matrix
                P_symp_mat_new = np.vstack((self.symp_matrix, temp_mat))
        else:
            P_symp_mat_new = np.vstack((self.symp_matrix, M_OP.symp_matrix))

        P_new_coeffs = np.hstack((self.coeff_vec, M_OP.coeff_vec))

        # cleanup run to remove duplicate rows (Pauliwords)
        return MajoranaOp(P_symp_mat_new, P_new_coeffs, phase_factors_included=True).cleanup()

    def __eq__(self, M_OP: "MajoranaOp"
                ) -> bool:
        """

        Args:
            M_OP:

        Returns:

        """
        check_1 = self.cleanup()
        check_2 =  M_OP.cleanup()
        if check_1.n_terms != check_2.n_terms:
            return False

        if check_1.n_sites != check_2.n_sites:
            if check_1.n_sites < check_2.n_sites:
                temp_mat_self = np.zeros((check_1.n_terms, check_2.n_sites))
                temp_mat_self[:, :check_1.n_sites] += check_1.symp_matrix
                temp_mat_M_OP = check_2.symp_matrix
            else:
                temp_mat_M_OP = np.zeros((check_2.n_terms, check_1.n_sites))
                temp_mat_M_OP[:, :check_2.n_sites] += check_2.symp_matrix
                temp_mat_self = check_1.symp_matrix
        else:
            temp_mat_M_OP = check_2.symp_matrix
            temp_mat_self = check_1.symp_matrix

        return (not np.einsum('ij->', np.logical_xor(temp_mat_self, temp_mat_M_OP)) and np.allclose(check_1.coeff_vec, check_2.coeff_vec))

    def __sub__(self,
                M_OP: "MajoranaOp"
                ) -> "MajoranaOp":
        """ Subtract from this MajoranaOp another MajoranaOp
        by negating the coefficients and summing
        """
        op_copy = M_OP.copy()
        op_copy.coeff_vec *= -1

        return self + op_copy

    def cleanup(self, zero_threshold=1e-15) -> "MajoranaOp":
        """ Remove duplicated rows of symplectic matrix terms, whilst summing
        the corresponding coefficients of the deleted rows in coeff
        """
        # convert sym form to list of ints
        int_list = self.symp_matrix @ (1 << np.arange(self.symp_matrix.shape[1])[::-1])
        re_order_indices = np.argsort(int_list)
        sorted_int_list = int_list[re_order_indices]

        sorted_symp_matrix = self.symp_matrix[re_order_indices]
        sorted_coeff_vec = self.coeff_vec[re_order_indices]

        # determine the first indices of each element in the sorted list (and ignore duplicates)
        elements, indices = np.unique(sorted_int_list, return_counts=True)
        row_summing = np.append([0], np.cumsum(indices))[:-1]  # [0, index1, index2,...]

        # reduced_symplectic_matrix = np.add.reduceat(sorted_symp_matrix, row_summing, axis=0)
        reduced_symplectic_matrix = sorted_symp_matrix[row_summing]
        reduced_coeff_vec = np.add.reduceat(sorted_coeff_vec, row_summing, axis=0)

        # return nonzero coeff terms!
        mask_nonzero = np.where(abs(reduced_coeff_vec) > zero_threshold)
        return MajoranaOp(reduced_symplectic_matrix[mask_nonzero],
                          reduced_coeff_vec[mask_nonzero], phase_factors_included=True)

    def to_OF_op(self):
        open_f_op = MajoranaOperator()
        for majorana_vec, ceoff in zip(self.symp_matrix, self.coeff_vec):
            maj_inds = self.term_index_list[majorana_vec.astype(bool)]

            open_f_op += MajoranaOperator(term=tuple(maj_inds.tolist()),
                                          coefficient=ceoff)
        return open_f_op


    def __repr__(self):
        return str(self)

    def __mul__(self,
                M_OP: "MajoranaOp"
                ) -> "MajoranaOp":
        """
        Right-multiplication of this MajoranaOp by another MajoranaOp
        """
        if self.n_sites != M_OP.n_sites:
            if self.n_sites < M_OP.n_sites:
                temp_mat_self = np.zeros((self.n_terms, M_OP.n_sites))
                temp_mat_self[:, :self.n_sites] += self.symp_matrix
                temp_mat_M_OP = M_OP.symp_matrix
                term_index_list = M_OP.term_index_list
            else:
                temp_mat_M_OP = np.zeros((M_OP.n_terms, self.n_sites))
                temp_mat_M_OP[:, :M_OP.n_sites] += M_OP.symp_matrix
                temp_mat_self = self.symp_matrix
                term_index_list = self.term_index_list
        else:
            temp_mat_M_OP = M_OP.symp_matrix
            temp_mat_self = self.symp_matrix
            term_index_list = self.term_index_list

        new_vec = np.zeros((self.n_terms * M_OP.n_terms, max(temp_mat_M_OP.shape[1],
                                                             temp_mat_self.shape[1])
                            ), dtype=int)
        new_coeff_vec = np.zeros((self.n_terms * M_OP.n_terms), dtype=complex)
        # new_coeff_vec = np.outer(self.coeff_vec, M_OP.coeff_vec).flatten()
        # sign_dict = {0: 1, 1: -1}

        ind = 0
        for ind1, vec1 in enumerate(temp_mat_self):
            for ind2, vec2 in enumerate(temp_mat_M_OP):
                new_vec[ind] = np.logical_xor(vec1, vec2).astype(int)
                _, reordering_sign = bubble_sort_maj(np.array((
                                                              *(term_index_list[vec1.astype(bool)]),
                                                              *(term_index_list[vec2.astype(bool)])
                                                                 )
                                                             )
                                                    )
                new_coeff_vec[ind] = self.coeff_vec[ind1] * M_OP.coeff_vec[ind2] * reordering_sign
                ind += 1

                # track changes to make operator in normal order
                # reordering_sign = sum(term * (sum(vec[i + 1:])) for i, term in enumerate(vec2[:-1])) % 2
                # new_coeff_vec[ind] *= sign_dict[reordering_sign]

                # new_coeff_vec[ind] *= reordering_sign
                # ind += 1

        return MajoranaOp(new_vec, new_coeff_vec, phase_factors_included=True).cleanup()


class majorana_rotations():
    def __init__(self, majorana_basis):
        self.majorana_basis = majorana_basis

        self.used_indices = None
        self.maj_rotations = None
        self.rotated_basis = None

    def _delete_reduced_rows(self, maj_op):
        z_term_check = np.logical_and(maj_op.symp_matrix[:, maj_op.even_inds],
                                      maj_op.symp_matrix[:, maj_op.odd_inds]).astype(int)

        single_z_rows = np.intersect1d(np.where(np.einsum('ij->i', z_term_check) == 1)[0],
                                       np.where(np.einsum('ij->i', maj_op.symp_matrix) == 2)[0])

        maj_z_pair_indices = set(np.where(np.einsum('ij->j', maj_op.symp_matrix[single_z_rows]) == 1)[0])

        singles_operator = None
        if len(single_z_rows) > 0:
            singles_operator = MajoranaOp(maj_op.symp_matrix[single_z_rows],
                                          maj_op.coeff_vec[single_z_rows],
                                          phase_factors_included=True)

        reduced_maj = MajoranaOp(np.delete(maj_op.symp_matrix, single_z_rows, axis=0),
                                 np.delete(maj_op.coeff_vec, single_z_rows, axis=0)
                                 , phase_factors_included=True)

        #         if (len(maj_z_pair_indices)%2)!=0:
        #             print('OP:', maj_op)
        #             print('Z inds', maj_z_pair_indices)
        #             raise ValueError('not Z inds')

        return set(maj_z_pair_indices), singles_operator, reduced_maj

    def get_rotations(self):
        self.used_indices = []
        self.maj_rotations = []
        self.rotated_basis = []

        maj_basis = self.majorana_basis.cleanup().copy()

        ## find any alread single terms
        maj_z_pair_indices, singles_operator, maj_basis = self._delete_reduced_rows(maj_basis)
        if singles_operator:
            self.rotated_basis.append(singles_operator)

        self.used_indices = set(maj_z_pair_indices)

        final_terms = self._recursively_rotate(maj_basis)
        if final_terms.n_terms!=0:
            raise ValueError('not fully reduced')

        return self.rotated_basis, self.maj_rotations

    def _recursively_rotate(self, maj_basis):

        maj_z_pair_indices, singles_operator, maj_basis = self._delete_reduced_rows(maj_basis)
        self.used_indices.update(maj_z_pair_indices)

        if maj_basis.n_terms == 0:
            # no more terms left
            return maj_basis

        # sort by most dense majorana operator (as will have fewest terms)
        sort_rows_by_weight = np.lexsort(maj_basis.symp_matrix.T)[::-1]

        # take first term (which is least dense)
        pivot_row = maj_basis.symp_matrix[sort_rows_by_weight][0]

        # get non identity positions (also ignores positions that have been rotated onto!)
        inds = np.where(np.logical_or(pivot_row[maj_basis.even_inds], pivot_row[maj_basis.odd_inds]))[0]
        indice_full = np.hstack((2 * inds, 2 * inds + 1))
        non_I = np.setdiff1d(indice_full, np.array(self.used_indices))

        # gives number of times modes in each position occur
        col_sum = np.einsum('ij->j', maj_basis.symp_matrix)

        # pivot_row * col_sum : gives positions where pivot term and where other single mode terms occur
        support = pivot_row * col_sum
        # want to take lowest index support (as this will allow unique terms)
        pivot_point = non_I[np.argmin(support[non_I])]

        if pivot_point % 2 == 0:
            pivot_point_even = pivot_point
            pivot_point_odd = pivot_point_even + 1  # 2i+1 index!
        else:
            pivot_point_odd = pivot_point
            pivot_point_even = pivot_point_odd - 1

        # take term we are rotating to single term
        rot_op = pivot_row.copy()
        pivot_maj = MajoranaOp(pivot_row, [1])

        # check if pivot term is Pauli Z term... if so then rotate pivot position to something else!
        if (pivot_row[pivot_point_even] + pivot_row[pivot_point_odd]) == 2:
            Z_rot = True
            # apply op like Pauli X on pivot position
            rot_op_inds = list(range(0, pivot_point_odd))

            # rotate Z onto different term
            maj_rot_op = MajoranaOp([[], rot_op_inds], [np.cos(np.pi / 4), 1j * np.sin(np.pi / 4)])
            rot_basis_out = (maj_rot_op * maj_basis * maj_rot_op.dagger).cleanup()
            rot_piv = (maj_rot_op * pivot_maj * maj_rot_op.dagger).cleanup()
            self.maj_rotations.append(maj_rot_op)

        elif rot_op[pivot_point_even] == rot_op[pivot_point_odd] == 0:
            raise ValueError('pivot error (identity term being used)')
        else:
            # no rotation needed!
            rot_basis_out = maj_basis.copy()
            rot_piv = pivot_maj.copy()

        rot_op2 = rot_piv.symp_matrix[0].copy()
        # pivot position is X or Y
        # if X use Y and if Y use X to make pauli Z on this position
        rot_op2[pivot_point_even] = (rot_op2[pivot_point_even] + 1) % 2
        rot_op2[pivot_point_odd] = (rot_op2[pivot_point_odd] + 1) % 2

        rot2_sym = np.zeros((2, len(pivot_row)))
        rot2_sym[1] = rot_op2
        maj_rot_op2 = MajoranaOp(rot2_sym, [np.cos(np.pi / 4), 1j * np.sin(np.pi / 4)])

        rot_basis_out2 = maj_rot_op2 * rot_basis_out * maj_rot_op2.dagger  # .cleanup()

        self.maj_rotations.append(maj_rot_op2)

        rotated_term = (maj_rot_op2 * rot_piv * maj_rot_op2.dagger).cleanup()

        self.rotated_basis.append(rotated_term)

        return self._recursively_rotate(rot_basis_out2)

