
import numpy as np

# overload SED namespace for our base object
from SED import SED as BaseGtlikeSED

from uw.like.Models import PowerLaw

from lande.utilities.tools import tolist
from uw.utilities import keyword_options

from lande.fermi.likelihood.save import name_to_spectral_dict, ts_dict, flux_dict, powerlaw_prefactor_dict, energy_dict
from lande.fermi.likelihood.superstate import SuperState
from lande.fermi.likelihood.models import build_gtlike_spectrum, build_pointlike_model
from lande.fermi.likelihood.fit import paranoid_gtlike_fit
from lande.fermi.likelihood.limits import GtlikePowerLawUpperLimit
from lande.fermi.likelihood.printing import summary

from . sed import SED


class GtlikeSED(SED):
        
    """ object to make SEDs using pyLikelihood. 
    
        Currently, this object only allows the SED
        points to be the same as the binning in
        the FT1 file. 

            Differences from pyLikelihood's SED code:
                * ul_algorithm XXX
        
        """
    defaults = SED.defaults + (
        ('bin_edges',            None, 'if specified, calculate the SED in these bins.'),
        ('freeze_background',    True, "don't refit background sources."),
        ('reoptimize_ts',       False, """ reoptimize the background model in the null hypothesis
                                           when calculating the TS. By default, don't do the 
                                           reoptimization. Note that this flag
                                           only makes sense when freeze_background=False"""),
        ('ul_algorithm',   'bayesian', "choices = 'frequentist', 'bayesian'"),
        ('powerlaw_index',          2, "fixed spectral index to assume when computing SED."),
        ('min_ts',                  4,"minimum ts in which to quote a SED points instead of an upper limit."),
        ('ul_confidence',        0.95,"confidence level for upper limit."),
        ('always_upper_limit',  False, """ Always compute an upper limit. Default is only when source is not significant. """),
        ('upper_limit_kwargs', dict(), 'Kwargs passed into IntegralUpperLimit.calc_int'),
    )


    @keyword_options.decorate(defaults)
    def __init__(self, like, name, *args, **kwargs):
        keyword_options.process(self, kwargs)

        self.like = like
        self.name = name

        if self.ul_algorithm not in BaseGtlikeSED.ul_choices:
            raise Exception("Upper Limit Algorithm %s not in %s" % (self.ul_algorithm,str(BaseGtlikeSED.ul_choices)))

        if self.reoptimize_ts and self.freeze_background:
            raise Exception("The reoptimize_ts=True flag should only be set when freeze_background=False")

        if self.bin_edges is not None:
            if not BaseGtlikeSED.good_binning(like, self.bin_edges):
                raise Exception("bin_edges is not commensurate with the underlying energy binning of pyLikelihood.")
            
            self.bin_edges = np.asarray(self.bin_edges)
            energy = np.sqrt(self.bin_edges[1:]*self.bin_edges[:-1])
        else:
            # These energies are always in MeV
            self.bin_edges = like.energies
            energy = like.e_vals

        self.lower=self.bin_edges[:-1]
        self.upper=self.bin_edges[1:]

        source=self.like.logLike.getSource(name) 
        self.init_spectrum=source.spectrum()
        self.init_model=build_pointlike_model(self.init_spectrum)

        self.results = dict(
            Name=name,
            spectrum=name_to_spectral_dict(like,name, errors=True, covariance_matrix=True),
        )
        self._calculate(like)

        super(GtlikeSED,self).__init__(self.results, **keyword_options.defaults_to_kwargs(self, SED))


    def _calculate(self,*args,**kwargs):
        """ Convert all units into sympy arrays after the initial calculation. """

        like = self.like
        name = self.name

        init_energes = like.energies[[0,-1]]

        # Freeze all sources except one to make sed of.
        all_sources = like.sourceNames()

        if name not in all_sources:
            raise Exception("Cannot find source %s in list of sources" % name)

        # make copy of parameter values + free parameters
        
        saved_state = SuperState(like)

        if self.freeze_background:
            if self.verbosity: print 'Freezeing all parameters'
            # freeze all other sources
            for i in range(len(like.model.params)):
                like.freeze(i)

        self.raw_results = []
        for i,(lower,upper) in enumerate(zip(self.lower,self.upper)):

            like.setEnergyRange(float(lower)+1, float(upper)-1)

            e = np.sqrt(lower*upper)

            if self.verbosity: print 'Calculating SED from %.0dMeV to %.0dMeV' % (lower,upper)

            # Scale the powerlaw to the input spectral model => helps with convergence
            init_dnde = self.init_model(e)
            model = PowerLaw(norm=init_dnde, index=self.powerlaw_index, e0=e)
            model.set_limits('norm',1e-10*init_dnde,1e10*init_dnde, scale=init_dnde)
            model.set_limits('index',-5,5)
            model.freeze('index')
            spectrum = build_gtlike_spectrum(model)

            spectrum = build_gtlike_spectrum(model)
            like.setSpectrum(name,spectrum)
            like.syncSrcParams(name)

            if self.verbosity:
                print 'Before fitting SED from %.0dMeV to %.0dMeV' % (lower,upper)
                print summary(like)

            paranoid_gtlike_fit(like, verbosity=self.verbosity)

            if self.verbosity:
                print 'After fitting SED from %.0dMeV to %.0dMeV' % (lower,upper)
                print summary(like)

            d = dict()
            self.raw_results.append(d)

            d['energy'] = energy_dict(emin=lower, emax=upper, energy_units=self.energy_units)
            d['flux'] = flux_dict(like, name, emin=lower,emax=upper, flux_units=self.flux_units, 
                                 errors=True, include_prefactor=True, prefactor_energy=e)
            d['prefactor'] = powerlaw_prefactor_dict(like, name, errors=False, minos_errors=True,
                                                    flux_units=self.flux_units)
            d['TS'] = ts_dict(like, name, verbosity=self.verbosity)

            if self.verbosity: print 'Calculating SED upper limit from %.0dMeV to %.0dMeV' % (lower,upper)

            if self.always_upper_limit or d['TS']['reoptimize'] < self.min_ts:
                ul = GtlikePowerLawUpperLimit(like, name,
                                              flux_units=self.flux_units,
                                              energy_units=self.energy_units,
                                              include_prefactor=True,
                                              prefactor_energy=e,
                                              upper_limit_kwargs=self.upper_limit_kwargs,
                                              verbosity=self.verbosity,
                                             )
                d['upper_limit'] = ul.todict()

        # revert to old model
        like.setEnergyRange(*init_energes)
        saved_state.restore()

        self._condense_results()

    def _condense_results(self):
        # convert results to standard self.results dict
        get = lambda a,b: np.asarray([i[a][b] for i in self.raw_results])
        get_units = lambda a,b: self.raw_results[0][a][b]
        get_limit = lambda a,b: np.asarray([i[a][b] if i.has_key(a) else np.nan for i in self.raw_results])
        self.results['Energy'] = dict(
            Lower=get('energy','emin'),
            Upper=get('energy','emax'),
            Value=get('energy','emiddle'),
            Units=get_units('energy','energy_units'))
        self.results['dNdE']=dict(
            Value=get('prefactor','prefactor'),
            Average_Error=(get('prefactor','prefactor_lower_err')+get('prefactor','prefactor_upper_err'))/2,
            Lower_Error=get('prefactor','prefactor_lower_err'),
            Upper_Error=get('prefactor','prefactor_upper_err'),
            Upper_Limit=get_limit('upper_limit','prefactor'),
            Units=get_units('prefactor','prefactor_units'))
        self.results['Ph_Flux']=dict(
            Value=get('flux','flux'),
            Average_Error=get('flux','flux_err'),
            Upper_Limit=get_limit('upper_limit','flux'),
            Units=get_units('flux','flux_units'))
        self.results['En_Flux']=dict(
            Value=get('flux','eflux'),
            Average_Error=get('flux','eflux_err'),
            Upper_Limit=get_limit('upper_limit','eflux'),
            Units=get_units('flux','eflux_units'))
        self.results['Test_Statistic']=get('TS','reoptimize')
        self.results['Significant']=get('TS','reoptimize')>self.min_ts

        self.results = tolist(self.results)

