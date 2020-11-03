import os
import numpy as np
import tensorflow as tf
import multiprocessing as mp

from os import sys
from random import choice, randint
from functools import partial
from tensorflow.keras.utils import to_categorical

from gostuff.gosgf import Sgf_game
from gostuff.gotypes import Player, Point
from gostuff.goboard import Board, GameState, Move
from gostuff.encoders.base import get_encoder_by_name
from gostuff.data.sgf_index import SGFIndex

def worker(jobinfo):
    try:
        clazz, size, encoder, filename = jobinfo
        features, labels = clazz(size=size, encoder=encoder).process(filename)
        return [features, labels]
    except (KeyboardInterrupt, SystemExit):
        raise Exception('>>> Exiting child process.')
    except:
        pass

class GoProcessor:
    def __init__(self, size=19, encoder='gogoboi', record_directory='/records'):
        self.size = size
        self.encoder_string = encoder
        self.encoder = get_encoder_by_name(encoder, self.size)
        self.record_dir = record_directory
        self.used_games = []

    def prep_data(self, data_type='train', num_samples=1000):
        index = SGFIndex(self.size)
        if not os.path.isdir(index.raw_dir):
            index.download()
        index.create_index()

        if num_samples > len(index.index):
            num_samples = len(index.index)
        total = num_samples
        while total != 0:
            if total > 200:
                num_samples = 200
            else:
                num_samples = total
            data = self.draw_data(index, num_samples)
            self.map_to_workers(data, data_type)
            total -= num_samples
            print('%s remaining' %(total))

    def draw_data(self, index, num_sample_games):
        games = []
        while len(games) < num_sample_games:
            game = choice(index.index)
            while game in self.used_games:
                game = choice(index.index)
            games.append(game)
            self.used_games.append(game)
        return games

    def map_to_workers(self, data, data_type):
        jobs = []
        for filename in data:
            jobs.append((self.__class__, self.size, self.encoder_string, filename))

        cores = mp.cpu_count()  
        pool = mp.Pool(processes=cores)
        p = pool.map_async(worker, jobs)
        try:
            results = p.get()
        except KeyboardInterrupt: 
            pool.terminate()
            pool.join()
            sys.exit(-1)
        pool.close()
        pool.join()

        features = []
        labels = []
        filename = self.record_dir+'/'+data_type+str(randint(1,9999))+'.tfrec'
        for pair in results:
            try:
                for feature in pair[0]:
                    features.append(feature)
                for label in pair[1]:
                    labels.append(label)
            except:
                continue
        self.tf_record_from_nparrays(features, labels, filename)

    def process(self, filename):
        total_examples = self.num_total_examples(filename)
        if not total_examples:
            return None
        shape = self.encoder.shape()
        feature_shape = np.insert(shape, 0, np.asarray([total_examples]))
        features = np.zeros(feature_shape)
        labels = np.zeros((total_examples,))

        counter = 0
        sgf = open(filename, 'r')
        sgf_content = sgf.read()
        sgf.close()
        sgf = Sgf_game.from_string(sgf_content)
        game_state = GameState.new_game(self.size)
        first_move_done = False

        for item in sgf.main_sequence_iter():
            color, move_tuple = item.get_move()
            point = None
            if color is not None:
                if move_tuple is not None:
                    row, col = move_tuple
                    point = Point(row + 1, col + 1)
                    move = Move.play(point)
                else:
                    move = Move.pass_turn()
                if first_move_done and point is not None:
                    features[counter] = self.encoder.encode(game_state)
                    labels[counter] = self.encoder.encode_point(point)
                    counter += 1
                game_state = game_state.apply_move(move)
                first_move_done = True

        labels = to_categorical(labels.astype(int), self.size * self.size)
        print(choice(['done', 'done!', 'done!!!'])) # Make sure SOMETHING is happening.
        return features, labels

    def num_total_examples(self, filename):
        total_examples = 0
        sgf = open(filename, 'r')
        sgf_content = sgf.read()
        sgf.close()
        sgf = Sgf_game.from_string(sgf_content)
        if sgf.get_handicap() is not None and sgf.get_handicap() != 0:
            return None
        first_move_done = False
        for item in sgf.main_sequence_iter():
            color, move = item.get_move()
            if color is not None:
                if first_move_done:
                    total_examples += 1
                first_move_done = True
        return total_examples

    def tf_record_from_nparrays(self, features, labels, record_file):
        if not os.path.isdir(self.record_dir):
            os.system('mkdir %s' %(self.record_dir))
        with tf.io.TFRecordWriter(record_file) as writer:
            for i in range(len(features)):
                writer.write(self.tf_example_from_nparrays(features[i], labels[i]))

    def tf_example_from_nparrays(self, feature, label):
        # Convert numpy arrays into string of TF Tensors.
        feature = tf.convert_to_tensor(feature, dtype='float32')
        feature = tf.io.serialize_tensor(feature)
        label = tf.convert_to_tensor(label, dtype='int64')
        label = tf.io.serialize_tensor(label)
        # Dictionary for each example. Values transformed to tf.train features.
        feature_dict = {
            'feature': self._bytes_feature(feature),
            'label': self._bytes_feature(label)
        }
        # Dictionary transformed to tf.train feature, then tf.train example.
        item = tf.train.Features(feature=feature_dict)
        example = tf.train.Example(features=item)
        return example.SerializeToString() 

    def _bytes_feature(self, value):
      # Returns a bytes_list from a string / byte.
      # BytesList won't unpack a string from an EagerTensor.
      if isinstance(value, type(tf.constant(0))):
          value = value.numpy()
      return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))

    def get_dataset(self, batch_size=32, data_type='train'):
        filenames = []
        for f in os.listdir(self.record_dir):
            if data_type in f:
                filenames.append(self.record_dir+'/'+f)
        dataset = self.load_dataset(filenames)
        dataset = dataset.shuffle(250000)
        dataset = dataset.prefetch(buffer_size=tf.data.experimental.AUTOTUNE)
        dataset = dataset.batch(batch_size)
        return dataset

    def load_dataset(self, filenames):
        ignore_order = tf.data.Options()
        ignore_order.experimental_deterministic = False
        dataset = tf.data.TFRecordDataset(filenames)
        dataset = dataset.with_options(ignore_order)
        dataset = dataset.map(partial(self.read_tfrecord), num_parallel_calls=tf.data.experimental.AUTOTUNE)
        return dataset

    def read_tfrecord(self, example_proto):
        example_description = {
            'feature': tf.io.FixedLenFeature([], tf.string),
            'label': tf.io.FixedLenFeature([], tf.string),
        }
        example = tf.io.parse_single_example(example_proto, example_description)
        feature = tf.ensure_shape(tf.io.parse_tensor(example['feature'], 
                                                     out_type='float32'), 
                                                    [self.encoder.shape()[0],self.encoder.shape()[1],self.encoder.shape()[2]])
        label = tf.ensure_shape(tf.io.parse_tensor(example['label'], out_type='int64'), [int(self.size*self.size)])
        return feature, label
