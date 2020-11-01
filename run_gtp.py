#!/usr/local/bin/python
from gostuff.agents.predict import load_prediction_agent
from gostuff.agents import termination
from gostuff.gtp import GTPFrontend
from argparse import ArgumentParser
import h5py

# Loads a model and passes it to GTP command/response

parser = ArgumentParser()
parser.add_argument('--model', type=str, required=True)
args = parser.parse_args()

# Load the model from an h5 file as a prediction agent.
model_file = h5py.File(args.model, 'r')
agent = load_prediction_agent(model_file)
# Wrap the prediction agent with termination strategy
strategy = termination.get('resign')
termination_agent = termination.TerminationAgent(agent, strategy)
# Pass to GTP
frontend = GTPFrontend(termination_agent)
frontend.run()
