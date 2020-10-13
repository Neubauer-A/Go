#!/usr/local/bin/python
from gostuff.gtp import GTPFrontend
from gostuff.agents.predict import load_prediction_agent
from gostuff.agents import termination
import h5py

model_file = h5py.File('/content/drive/My Drive/Colab Notebooks/Go/gostuff/models/ggb.h5', 'r')
agent = load_prediction_agent(model_file)
strategy = termination.get('resign')
termination_agent = termination.TerminationAgent(agent, strategy)

frontend = GTPFrontend(termination_agent)
frontend.run()
