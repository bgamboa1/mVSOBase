import os
import pyomo.environ
import shutil
import urbs
from datetime import datetime
from pyomo.opt.base import SolverFactory

# SCENARIOS

def scenario_generator(scenario_name, pv_cost, bat_cost, diesel_gen_cost, 
                       fuel_cost):
    def scenario(data):
        # short-hands for individual DataFrames
        com = data['commodity']
        pro = data['process']
        sto = data['storage']
        
        # row indices for entries
        diesel = ('StRupertMayer', 'Diesel', 'Stock')
        pv_plant = ('StRupertMayer', 'Photovoltaics')
        diesel_gen = ('StRupertMayer', 'Diesel generator')
        battery = ('StRupertMayer', 'Battery', 'Electricity')
        
        # change investment/fuel cost values according to arguments
        pro.loc[pv_plant, 'inv-cost'] = pv_cost  # EUR/kW
        sto.loc[battery, 'inv-cost-c'] = bat_cost  # EUR/kWh
        pro.loc[diesel_gen, 'inv-cost'] = diesel_gen_cost  # EUR/kW
        com.loc[diesel, 'price'] = fuel_cost  # EUR/kWh
        
        # for the 3 investment costs, also change fix costs accordingly
        pro.loc[pv_plant, 'fix-cost'] = 0.05 * pv_cost
        sto.loc[battery, 'fix-cost-c'] = 0.05 * bat_cost
        pro.loc[diesel_gen, 'fix-cost'] = 0.1 * diesel_gen_cost
        
        return data
    scenario.__name__ = scenario_name  # used for result filenames
    return scenario

def prepare_result_directory(result_name):
    """ create a time stamped directory within the result folder """
    # timestamp for result directory
    now = datetime.now().strftime('%Y%m%dT%H%M')

    # create result directory if not existent
    result_dir = os.path.join('result', '{}-{}'.format(result_name, now))
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)

    return result_dir


def setup_solver(optim, logfile='solver.log'):
    """ """
    if optim.name == 'gurobi':
        # reference with list of option names
        # http://www.gurobi.com/documentation/5.6/reference-manual/parameters
        optim.set_options("logfile={}".format(logfile)) 
        # optim.set_options("timelimit=7200")  # seconds
        # optim.set_options("mipgap=5e-4")  # default = 1e-4
    elif optim.name == 'glpk':
        # reference with list of options
        # execute 'glpsol --help'
        optim.set_options("log={}".format(logfile))
        # optim.set_options("tmlim=7200")  # seconds
        # optim.set_options("mipgap=.0005")
    else:
        print("Warning from setup_solver: no options set for solver "
              "'{}'!".format(optim.name))
    return optim

def run_scenario(input_file, timesteps, scenario, result_dir, plot_periods={}):
    """ run an urbs model for given input, time steps and scenario

    Args:
        input_file: filename to an Excel spreadsheet for urbs.read_excel
        timesteps: a list of timesteps, e.g. range(0,8761)
        scenario: a scenario function that modifies the input data dict
        result_dir: directory name for result spreadsheet and plots

    Returns:
        the urbs model instance
    """

    # scenario name, read and modify data for scenario
    sce = scenario.__name__
    data = urbs.read_excel(input_file)
    data = scenario(data)

    # create model
    prob = urbs.create_model(data, timesteps)

    # refresh time stamp string and create filename for logfile
    now = prob.created
    log_filename = os.path.join(result_dir, '{}.log').format(sce)

    # solve model and read results
    optim = SolverFactory('gurobi')  # cplex, glpk, gurobi, ...
    optim = setup_solver(optim, logfile=log_filename)
    result = optim.solve(prob, tee=True)

    # copy input file to result directory
    shutil.copyfile(input_file, os.path.join(result_dir, input_file))
	
	# write report to spreadsheet
    urbs.report(
        prob,
        os.path.join(result_dir, '{}.xlsx').format(sce),
        prob.com_demand, prob.sit)

    urbs.result_figures(
        prob, 
        os.path.join(result_dir, '{}'.format(sce)),
        plot_title_prefix=sce.replace('_', ' ').title(),
        periods=plot_periods, power_unit='kW', energy_unit='kWh',
        figure_size=(24,4))
    return prob

if __name__ == '__main__':
    input_file = '1node.xlsx'
    result_name = os.path.splitext(input_file)[0]  # cut away file extension
    result_dir = prepare_result_directory(result_name)  # name + time stamp

    # simulation timesteps
    (offset, length) = (0, 8760)  # time step selection
    timesteps = range(offset, offset+length+1)
    
    # plotting timesteps
    periods = {
        '01-jan': range(   1,  745),
        '02-feb': range( 745, 1417),
        '03-mar': range(1417, 2161),
        '04-apr': range(2161, 2881),
        '05-may': range(2881, 3625),
        '06-jun': range(3625, 4345),
        '07-jul': range(4345, 5089),
        '08-aug': range(5089, 5833),
        '09-sep': range(5833, 6553),
        '10-oct': range(6553, 7297),
        '11-nov': range(7297, 8017),
        '12-dec': range(8017, 8761)
    }
    
    # add or change plot colors
    my_colors = {
        'Demand': (0, 0, 0),
        'Diesel generator': (218, 215, 203),
        'Electricity': (0, 51, 89),
        'Photovoltaics': (0, 101, 189),
        'Storage': (100, 160, 200)}
    for country, color in my_colors.items():
        urbs.COLORS[country] = color

    # select scenarios to be run
    scenarios = [
        #                  name     pv   bat  gen  fuel
        # High battery cost, PV high to low
        scenario_generator('s01', 2000, 1000, 200, 0.09),
        scenario_generator('s02', 1500, 1000, 200, 0.09),
        scenario_generator('s03', 1000, 1000, 200, 0.09),
        scenario_generator('s04',  500, 1000, 200, 0.09),
        # Medium battery cost, PV medium to low
        scenario_generator('s05', 1000,  500, 200, 0.09),
        scenario_generator('s06',  500,  500, 200, 0.09),
        # Low battery cost, PV medium to low
        scenario_generator('s07', 1000,  200, 200, 0.09),
        scenario_generator('s08',  500,  200, 200, 0.09),
        # High fuel cost scenarios, PV and battery medium
        scenario_generator('s09',  500,  500, 200, 0.18),
        scenario_generator('s10',  500,  500, 200, 0.27)]

    for scenario in scenarios:
        prob = run_scenario(input_file, timesteps, scenario, 
                            result_dir, plot_periods=periods)
