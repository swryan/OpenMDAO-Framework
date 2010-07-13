"""
    conmindriver.py - Driver for the CONMIN optimizer.
"""

# pylint: disable-msg=C0103

#public symbols
__all__ = ['CONMINdriver']



from sys import float_info

# pylint: disable-msg=E0611,F0401
from numpy import ndarray, array, zeros, ones
from numpy import int as numpy_int

from enthought.traits.api import on_trait_change, TraitError
                                 
import conmin.conmin as conmin

from openmdao.main.api import Case, Driver, Expression, ExpressionList
from openmdao.main.exceptions import RunStopped
from openmdao.lib.traits.float import Float
from openmdao.lib.traits.int import Int
from openmdao.lib.traits.array import Array


class _cnmn1(object):
    """Just a primitive data structure for storing cnmnl common block data"""
    
    def __init__(self):
        self.clear()

    # Note: These values aren't the defaults. This object instantiates with
    # "cleared" values. The true default values (as denoted in the corresponding
    # traits) are assigned later.
    def clear(self):
        """ Clear values. """
        self.ndv = 0
        self.ncon = 0
        self.nside = 0
        self.nacmx1 = 0
        self.infog = 0
        self.info = 0
        self.nfdg = 0
        self.icndir = 0
        self.nscal = 0
        self.fdch = 0.0
        self.fdchm = 0.0
        self.ct = 0.
        self.ctmin = 0.
        self.ctlmin = 0.
        self.theta = 0.
        self.phi = 0.
        self.delfun = 0.
        self.dabfun = 1.e-8
        self.linobj = 0
        self.itrm = 0
        self.alphax = 0.
        self.abobj1 = 0.
        self.ctl = 0.
        self.igoto = 0
        self.nac = 0
        self.iter = 0
        self.iprint = 0
        self.itmax = 0
 
class _consav(object):
    """Just a primitive data structure for storing consav common block data"""
    
    def __init__(self):
        self.clear()
    
    def clear(self):
        """ Clear values. """
        self.dm1 = 0.0
        self.dm2 = 0.0
        self.dm3 = 0.0
        self.dm4 = 0.0
        self.dm5 = 0.0
        self.dm6 = 0.0
        self.dm7 = 0.0
        self.dm8 = 0.0
        self.dm9 = 0.0
        self.dm10 = 0.0
        self.dm11 = 0.0
        self.dm12 = 0.0
        self.dct = 0.0
        self.dctl = 0.0
        self.phi = 0.0
        self.abobj = 0.0
        self.cta = 0.0
        self.ctam = 0.0
        self.ctbm = 0.0
        self.obj1 = 0.0
        self.slope = 0.0
        self.dx = 0.0
        self.dx1 = 0.0
        self.fi = 0.0
        self.xi = 0.0
        self.dftdf1 = 0.0
        self.alp = 0.0
        self.fff = 0.0
        self.a1 = 0.0
        self.a2 = 0.0
        self.a3 = 0.0
        self.a4 = 0.0
        self.f1 = 0.0
        self.f2 = 0.0
        self.f3 = 0.0
        self.f4 = 0.0
        self.cv1 = 0.0
        self.cv2 = 0.0
        self.cv3 = 0.0
        self.cv4 = 0.0
        self.app = 0.0
        self.alpca = 0.0
        self.alpfes = 0.0
        self.alpln = 0.0
        self.alpmin = 0.0
        self.alpnc = 0.0
        self.alpsav = 0.0
        self.alpsid = 0.0
        self.alptot = 0.0
        self.rspace = 0.0
        self.idm1 = 0
        self.idm2 = 0
        self.idm3 = 0
        self.jdir = 0
        self.iobj = 0
        self.kobj = 0
        self.kcount = 0
        self.ncal = [0, 0]
        self.nfeas = 0
        self.mscal = 0
        self.ncobj = 0
        self.nvc = 0
        self.kount = 0
        self.icount = 0
        self.igood1 = 0
        self.igood2 = 0
        self.igood3 = 0
        self.igood4 = 0
        self.ibest = 0
        self.iii = 0
        self.nlnc = 0
        self.jgoto = 0
        self.ispace = [0, 0]
        
class CONMINdriver(Driver):
    """ Driver wrapper of Fortran version of CONMIN. 
        
    
.. todo:: Make CONMIN's handling of user calculated gradients 
          accessible through CONMINdriver
            
    """
    
    # pylint: disable-msg=E1101
    design_vars = ExpressionList(iotype='out',
       desc='An array of design variable names. These names can include array '
             'indexing.')
    
    constraints = ExpressionList(iotype='in',
            desc= 'A list of expression strings indicating constraints.'
            ' A value of < 0 for the expression indicates that the constraint '
            'is violated.')
    
    objective = Expression(iotype='in',
                desc= 'A string containing the objective function expression.')
    
    upper_bounds = Array(zeros(0.,'d'), iotype='in',
        desc='Array of constraints on the maximum value of each design variable.')
    
    lower_bounds = Array(zeros(0.,'d'), iotype='in',
        desc='Array of constraints on the minimum value of each design variable.')

    scal = Array(zeros(0.,'d'), iotype='in', 
        desc='Array of scaling factors for the design variables.')

    cons_is_linear = Array(zeros(0,'d'), dtype=numpy_int, iotype='in', 
        desc='Array designating whether each constraint is linear.')
                 
    # Control parameters for CONMIN.
    # CONMIN has quite a few parameters to give the user control over aspects
    # of the solution. 
    
    iprint = Int(0, iotype='in', desc='Print information during CONMIN '
                    'solution. Higher values are more verbose')
    itmax = Int(10, iotype='in', desc='Maximum number of iterations before '
                    'termination')
    fdch = Float(.01, iotype='in', desc='Relative change in design variables '
                      'when calculating finite difference gradients')
    fdchm = Float(.01, iotype='in', desc='Minimum absolute step in finite '
                      'difference gradient calculations')
    icndir = Float(0, iotype='in', desc='Conjugate gradient restart '
                      'parameter')
    nscal = Float(0, iotype='in', desc='Scaling control parameter -- '
                      'controls scaling of decision variables')
    nfdg = Float(0, iotype='in', desc='User-defined gradient flag (not yet '
                      'supported)')
    ct = Float(-0.1, iotype='in', desc='Constraint thickness parameter.')
    ctmin = Float(0.004, iotype='in', desc='Minimum absoluate value of ct '
                      'used in optimization.')
    ctl = Float(-0.01, iotype='in', desc='Constraint thickness parameter for '
                      'linear and side constraints.')
    ctlmin = Float(0.001, iotype='in', desc='Minimum absoluate value of ctl '
                      'used in optimization.')
    theta = Float(1.0, iotype='in', desc='Mean value of the push-off factor '
                      'in the method of feasible directions.')
    phi = Float(5.0, iotype='in', desc='Participation coefficient - penalty '
                      'parameter that pushes designs towards the feasible '
                      'region.')
    delfun = Float(0.001, iotype='in', low=0.0001, 
                   desc='Relative convergence tolerance')
    dabfun = Float(0.001, iotype='in', low=1.0e-10, 
                   desc='Absolute convergence tolerance')
    linobj = Int(0, iotype='in', desc='Linear objective function flag')
    itrm = Int(3, iotype='in', desc='Number of consecutive iterations to '
                      'indicate convergence (relative or absolute)')
        
    # Extra variables for printing
    printvars = ExpressionList(iotype='in', desc='list of extra variables to'
                               'output in the recorder')
    
    def __init__(self, doc=None):
        super(CONMINdriver, self).__init__( doc)
        
        # Save data from common blocks into our CONMINdriver object
        self.cnmn1 = _cnmn1()
        self.consav = _consav()
        
        self.iter_count = 0

        # define the CONMINdriver's private variables
        # note, these are all resized in config_conmin
        
        # basic stuff
        self.design_vals = zeros(0,'d')
        self._scal = zeros(0,'d')
        self.cons_active_or_violated = zeros(0, 'i') 
        
        # gradient of objective w.r.t x[i]
        self.df = zeros(0, 'd')

        # move direction in the optimization space
        self.s = zeros(0, 'd')
        self.gradients = zeros(0, 'd')

        # temp storage
        self._b = zeros(0, 'd')
        self._c = zeros(0, 'd')
        self._ms1 = zeros(0, 'i')
         
        # temp storage for constraints
        self.g1 = zeros(0,'d')
        self.g2 = zeros(0,'d')

        
    def execute(self):
        """Perform the optimization."""
        # set conmin array sizes and such
        self._config_conmin()
        self.cnmn1.igoto = 0
        self.iter_count = 0
        
        # get the initial values of the design variables
        # check if any min/max constraints are violated by initial values
        for i, val in enumerate(self.design_vars):
            self.design_vals[i] = val.evaluate()
            
            if self.design_vals[i] > self.upper_bounds[i]:
                if (self.design_vals[i] - self.upper_bounds[i]) < self.ctlmin:
                    self.design_vals[i] = self.upper_bounds[i]
                else:
                    self.raise_exception('maximum exceeded for initial value'
                                         ' of: %s' % val, ValueError)

            if self.design_vals[i] < self.lower_bounds[i]:
                if (self.lower_bounds[i] - self.design_vals[i] ) < self.ctlmin:
                    self.design_vals[i] = self.lower_bounds[i]
                else:
                    self.raise_exception('minimum exceeded for initial value'
                                         ' of: %s' % val, ValueError)

        # perform an initial run for self-consistency
        self.run_iteration()

        # update constraint value array
        for i, v in enumerate(self.constraints):
            self.constraint_vals[i] = v.evaluate()
        #self._logger.debug('%s: new iteration' % self.get_pathname())
        #self._logger.debug('objective = %s' % self.objective)
        #self._logger.debug('design vars = %s' % self.design_vars)
        
        # loop until optimized
        while self.cnmn1.igoto or self.iter_count == 0:
            
            if self._stop:
                self.raise_exception('Stop requested', RunStopped)

            # calculate objective
            try:
                self.cnmn1.obj = self.objective.evaluate()
            except Exception as err:
                self.raise_exception('error evaluating objective function: %s' % str(err), 
                                     RuntimeError)
                    
            #self._logger.debug('iter_count = %d' % self.iter_count)
            #self._logger.debug('objective = %f' % self.cnmn1.obj)
            #self._logger.debug('design vals = %s' % self.design_vals[:-2])
            
# TODO: 'step around' ill-behaved cases.
            
            # common blocks are saved before, and loaded after execution
            self._load_common_blocks()
            
            try:
                (self.design_vals,
                 self._scal, self.gradients, self.s,
                 self.g1, self.g2, self._b, self._c,
                 self.cons_is_linear,
                 self.cons_active_or_violated, self._ms1) = \
                     conmin.conmin(self.design_vals,
                                   self._lower_bounds, self._upper_bounds,
                                   self.constraint_vals,
                                   self._scal, self.df,
                                   self.gradients,
                                   self.s, self.g1, self.g2, self._b, self._c,
                                   self.cons_is_linear,
                                   self.cons_active_or_violated, self._ms1)
            except Exception, err:
                self._logger.error(str(err))
                raise
            
            # common blocks are saved before, and loaded after execution
            self._save_common_blocks()
            
            # update the design variables in the model
            dvals = [float(val) for val in self.design_vals[:-2]]
            for var, val in zip(self.design_vars, dvals):
                var.set(val)
            
            # calculate objective and constraints
            if self.cnmn1.info == 1:
                
                # update the model
                self.run_iteration()
            
                # update constraint value array
                for i, v in enumerate(self.constraints):
                    self.constraint_vals[i] = v.evaluate()
                #self._logger.debug('constraints = %s'%self.constraint_vals)
                    
            # calculate gradient of constraints and graident of objective
            elif self.cnmn1.info == 2:
                
                # Placeholder for future use of component gradient calc.
                
                # User-defined gradients for objective and constraints
                if self.cnmn1.nfdg == 1:
                    self.raise_exception('User defined gradients not yet \
                               supported for constraints', NotImplementedError)
                    
                # User-defined gradients for just the objective
                elif self.cnmn1.nfdg == 2:
                    self.raise_exception('User defined gradients not yet \
                               supported', NotImplementedError)
                
            else:
                self.raise_exception('Unexpected value for flag INFO returned \
                        from CONMIN', RuntimeError)

            # Iteration count comes from CONMIN. You can't just count over the
            # loop because some cycles do other things (e.g., numerical
            # gradient calculation)
            if self.iter_count != self.cnmn1.iter:
                    
                self.iter_count = self.cnmn1.iter 
                
                if self.recorder:
                    # Write out some relevant information to the recorder
                    case_input = []
                    for var, val in zip(self.design_vars, dvals):
                        case_input.append([var, None, val])
                        
                    for var in self.printvars:
                        case_input.append([var, None, var.evaluate()])
                
                    case_output = []
                    case_output.append(["objective", None, self.cnmn1.obj])
                
                    for i, val in enumerate(self.constraint_vals):
                        case_output.append(["Constraint%d" % i, None, val])
                    
                    self.recorder.record(Case(case_input, case_output, 
                                              'case%s' % self.iter_count))
                        

    def _config_conmin(self):
        """Set up arrays for the FORTRAN conmin routine, and perform some
        validation and make sure that array sizes are consistent.
        """
        self.cnmn1.clear()
        self.consav.clear()
        
        if not isinstance(self.objective, basestring):
            self.raise_exception('no objective specified', RuntimeError)
        
        # size arrays based on number of design variables
        num_dvs = len(self.design_vars)
        self.design_vals = zeros(num_dvs+2, 'd')

        if num_dvs < 1:
            self.raise_exception('no design variables specified', RuntimeError)
            
        # create lower_bounds array
        if len(self.lower_bounds) > 0:
            self._lower_bounds = zeros(len(self.lower_bounds)+2)
            if len(self.lower_bounds) != num_dvs:
                msg = 'size of new lower bound array (%d) does not match ' + \
                      'number of design vars (%d)'
                self.raise_exception(msg % (len(self.lower_bounds), num_dvs), \
                                     ValueError)
            for i, lb in enumerate(self.lower_bounds):
                self._lower_bounds[i] = lb
        else:
            self._lower_bounds = array(([-float_info.max]*num_dvs) + \
                                                 [0., 0.])
            
            
        # create upper bounds array
        if len(self.upper_bounds) > 0:
            self._upper_bounds = zeros(len(self.upper_bounds)+2)
            if len(self.upper_bounds) != num_dvs:
                msg = 'size of new upper bound array (%d) does not match ' + \
                      'number of design vars (%d)'
                self.raise_exception(msg % (len(self.upper_bounds), num_dvs), \
                                     ValueError)
            
            for i, ub in enumerate(self.upper_bounds):
                self._upper_bounds[i] = ub
        else:
            self._upper_bounds = array(([float_info.max]*num_dvs) + \
                                                 [0., 0.])

        # Check if the upper and lower bounds are swapped    
        for i, val in enumerate(self._lower_bounds):
            if val > self._upper_bounds[i]:
                self.raise_exception('lower bound greater than upper bound ' + \
                    'for design variable (%s)'%self.design_vars[i], ValueError)

                
        # create array for scaling of the design vars
        self._scal = ones(num_dvs+2)
        if len(self.scal) > 0:
            if len(self.scal) != num_dvs:
                msg = 'size of scale factor array (%d) does not match ' + \
                      'number of design vars (%d)'
                self.raise_exception(msg % (len(self.scal), num_dvs), \
                                     ValueError)
            
            for i, scale_factor in enumerate(self.scal):
                self._scal[i] = scale_factor
            
        self.df = zeros(num_dvs+2, 'd')
        self.s = zeros(num_dvs+2, 'd')
        
        # size constraint related arrays
        length = len(self.constraints) + 2*num_dvs
        self.constraint_vals = zeros(length, 'd')
        
        # temp storage of constraint and design vals
        self.g1 = zeros(length, 'd') 
        
        # temp storage of constraint vals
        self.g2 = zeros(length, 'd') 
        
        # if constraint i is known to be a linear function of design vars, 
        # the user can set cons_is_linear[i] to 1, otherwise set it to 0. This
        # is not essential and is for efficiency only.
        if len(self.cons_is_linear) == 0:
            self.cons_is_linear = zeros(length, 'i') 
        else:
            if len(self.cons_is_linear) != length:
                self.raise_exception('size of cons_is_linear (%d) does not \
                                      match number of constraints (%d)'%
                               (len(self.cons_is_linear),length), ValueError)
        
        self.cnmn1.ndv = num_dvs
        self.cnmn1.ncon = len(self.constraints)
        
        if len(self.lower_bounds) > 0 or len(self.upper_bounds) > 0:
            self.cnmn1.nside = 2*num_dvs
        else:
            self.cnmn1.nside = 0

        self.cnmn1.nacmx1 = max(num_dvs,
                                len(self.constraints)+self.cnmn1.nside)+1
        n1 = num_dvs+2
        n3 = self.cnmn1.nacmx1
        n4 = max(n3, num_dvs)
        n5 = 2*n4
                
        # array of active or violated constraints (ic in CONMIN)
        self.cons_active_or_violated = zeros(n3, 'i')
        self.gradients = zeros((int(n1), int(n3)), 'd')
        # temp storage
        self._b = zeros((int(n3), int(n3)), 'd')
        # temp storage
        self._c = zeros(n4, 'd')
        # temp storage
        self._ms1 = zeros(n5, 'i')

        # Load all of the user-changeable parameters into the common block
        
        self.cnmn1.iprint = self.iprint
        self.cnmn1.itmax = self.itmax
        self.cnmn1.fdch = self.fdch
        self.cnmn1.fdchm = self.fdchm
        self.cnmn1.icndir = self.icndir
        self.cnmn1.nscal = self.nscal
        self.cnmn1.nfdg = self.nfdg
        self.cnmn1.ct = self.ct
        self.cnmn1.ctmin = self.ctmin
        self.cnmn1.ctl = self.ctl
        self.cnmn1.ctlmin = self.ctlmin
        self.cnmn1.theta = self.theta
        self.cnmn1.phi = self.phi
        self.cnmn1.dabfun = self.dabfun
        self.cnmn1.delfun = self.delfun
        self.cnmn1.linobj = self.linobj
        self.cnmn1.itrm = self.itrm
        

    @on_trait_change('objective') 
    def _expr_changed(self, obj, name, old, new):
        """ Check objective on change"""
        
        expr = getattr(obj, name)
        try:
            # force checking for existence of vars referenced in expression
            expr.refs_valid()  
        except (AttributeError, RuntimeError), err:
            msg = "invalid value '%s' for input ref variable '%s': %s"
            self.raise_exception( msg % (str(expr), name, err), TraitError)
        
    @on_trait_change('constraints, design_vars') 
    def _exprlist_changed(self, obj, name, old, new):
        """ Check constraints and design variables on change"""

        exprevals = getattr(obj, name)
        for i, expr in enumerate(exprevals):
            try:
                # force checking for existence of vars referenced in expression
                expr.refs_valid()  
            except (AttributeError, RuntimeError), err:
                msg = "invalid value '%s' for input ref variable '%s[%d]': %s"
                self.raise_exception( msg % \
                    (str(expr), name, i, err), TraitError)
        
    def _load_common_blocks(self):
        """ Reloads the common blocks using the intermediate info saved in the
            class.
            """
        
        for name, value in self.cnmn1.__dict__.items():
            setattr( conmin.cnmn1, name, value )
        
        for name, value in self.consav.__dict__.items():
            setattr( conmin.consav, name, value  )
        
        
    def _save_common_blocks(self):
        """" Saves the common block data to the class to prevent trampling by
        other instances of CONMIN.
        """
        common = self.cnmn1
        for name, value in common.__dict__.items():
            if isinstance(value, ndarray):
                setattr(common, name, getattr(conmin.cnmn1, name).copy())
            else:
                setattr(common, name, type(value)(getattr(conmin.cnmn1, name)))
        
        consav = self.consav
        for name, value in consav.__dict__.items():
            if isinstance(value, ndarray):
                setattr(consav, name, getattr(conmin.consav, name).copy())
            else:
                setattr(consav, name, type(value)(getattr(conmin.consav, name)))
        
        
