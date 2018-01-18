'''
Implementation of the network thats learns ono the expert policies data set
'''

import tensorflow as tf
import parameters
import numpy as np
from numpy.random import choice
import time

from Utils import variable_summaries

class Neural_Network():

    def __init__(self, game):
        '''
        Initialises Neural Network parameters, based on the game parameters
        :param game: (str) the game to be played
        '''
        self.game = game
        self.parameters = getattr(parameters, game)

        self.input_W = self.parameters['input_W']
        self.input_H = self.parameters['input_H']
        self.input_C = self.parameters['input_C']
        self.n_actions = self.parameters['n_actions']
        self.past_memory = self.parameters['past_memory']
        self.learning_rate = self.parameters['learning_rate']
        self.n_epochs = self.parameters['n_epochs']
        self.batch_size = self.parameters['batch_size']
        self.n_hidden_layers = self.parameters['n_hidden_layers']
        self.n_hidden_layers_nodes = self.parameters['n_hidden_layers_nodes']
        self.optimizer = self.parameters['optimizer']

        self.n_input_features = self.input_H*self.input_W*self.input_C*self.past_memory

        if game == 'pong':
            self.build_model = self._build_network_full_images
            self.placeholders = self._placeholders_full_images

        with open('Data/{}/states.txt'.format(game), 'r') as file:
            lines = file.readlines()
            self.set_size = len(lines)


    def fit(self, device, save_path, training_lap, writer, start_time):
        '''
        Fits the Network to the set currently in Data/$game
        :param device: (str) '/GPU:0' or '/CPU:0'
        :param save_path: (str) path to save the trained model, learning curves are to be saved with the global writer
        :param training_lap: (int) the iteration in SMILE or DAGGER
        :param writer: (tf.summary.FileWriter) the global file writer that saves all learning curves
        :param start_time: (time) current time
        '''

        print('Sarting Lap : {} Training ...')
        print(' -- Initializing network ...')
        with tf.device(device):
            with tf.name_scope('Inputs'):
                X, y, training = self.placeholders(self.n_input_features, self.n_actions)

            network = self.build_model(X, self.n_input_features, self.n_hidden_layers_nodes, self.n_actions, training)

            with tf.name_scope('Loss'):
                loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(labels=y, logits=network,
                                                                              name='Entropy'), name='Reduce_mean')
                tf.summary.scalar('loss', loss, collections=['train_{}'.format(training_lap)])
                merged_summary = tf.summary.merge_all('train')

            with tf.name_scope('Optimizer'):
                optimizer = self.optimizer(self.learning_rate)
                minimizer = optimizer.minimize(loss)

            print(' -- Network initialized')
            print(' -- Starting training ...')
            saver = tf.train.Saver()
            init = tf.global_variables_initializer()
            with tf.Session(config=tf.ConfigProto(allow_soft_placement=True, log_device_placement=True)) as sess:
                sess.run(init, {training: True})
                for epoch in range(self.n_epochs):
                    for batch_number in range(int(self.set_size/self.batch_size)):
                        X_batch, y_batch =  self._make_batch_full_images(self.game, self.batch_size, self.n_features, self.n_actions, self.past_memory)
                        cost = 0
                        for ind in range(self.batch_size):
                            _, c, summary = sess.run([minimizer, loss, merged_summary], feed_dict={X: X_batch[ind, :], y: y_batch[ind, :]})
                            cost += c

                        if batch_number % 100 == 0:
                            writer.add_summary(summary, batch_number + epoch * int(self.set_size/self.batch_size))
                            print(' |-- Epoch {0} Batch {1} done ({2}) :'.format(epoch, batch_number, time.strftime("%H:%M:%S",
                                                                                    time.gmtime(time.time() - start_time))))
                            print(' |--- Avg cost = {}'.format(cost/self.batch_size))

                saver.save(sess, save_path)
                sess.close()

            print(' -- Training over')
            print(' -- Model saved to : {}'.format(save_path))


    def _make_batch_full_images(self, game, batch_size, n_features, n_actions, past_memory):
        '''
        Makes a batch from the currently saved data set. For image only features.
        :param game: (str) the game to be played
        :param batch_size: (int) the size of the batch to make
        :param n_features: (int) number of input features
        :param n_actions: (int) number of output features
        :param past_memory: (int) number of images to take before the state
        :return: (np array) (np array)
        '''

        with open('Data/{}/states.txt'.format(game), 'r') as file:
            lines = choice(file.readlines(), batch_size)

        X_batch = np.zeros([batch_size, n_features, 1])
        y_batch = np.zeros([batch_size, n_actions])
        for _ in range(batch_size):
            state_dict = np.load('Data/{0}/states/dict_{1}.npy'.format(game, lines[_]))
            img_list = []
            for _img in range(past_memory):
                img = np.load(state_dict['image_{}.jpg'.format(_img)])
                img_flat = img.flatten()
                img_list.append(img_flat)

            X_batch[_,:] = np.concatenate(img_list)
            y_batch[_,:] = np.load(state_dict['action'])

        return X_batch, y_batch


    def _build_network_full_images(self, input, n_features, n_hidden_layer_nodes, output_size, training):
        '''
        Builds a one layer neural network. For image only features.
        :param input: (tensor)
        :param n_features: (int)
        :param n_hidden_layer_nodes: (int) number of nodes in the hidden layer
        :param output_size: (int)
        :param training: (Boolean) if training dropout is activated
        :return: (tensor)
        '''

        with tf.name_scope('Layers'):
            hidden_out = self._linear_layer(input, n_hidden_layer_nodes, n_features, name='Hidden_Layer')
            with tf.name_scope('Dropout'):
                if training:
                    hidden_out = tf.nn.dropout(hidden_out, keep_prob=0.9, name='Dropout')

            out = self._linear_layer(hidden_out, output_size, n_hidden_layer_nodes, name='Hidden_Layer')

        return out


    def _linear_layer(self, input, dim_0, dim_1, name='', out_layer=False):
        '''
        Builds a linear layer
        :param input: (tensor)
        :param dim_0: (int)
        :param dim_1: (int)
        :param name: (str) name of the layer
        :param out_layer: (Boolean) if True, no activation
        :return: (tensor)
        '''

        with tf.name_scope(name):
            with tf.name_scope('Weights'):
                W =  tf.Variable(tf.truncated_normal([dim_0, dim_1], stddev=0.1), name='W')
                variable_summaries(W)
                b = tf.Variable(tf.zeros([dim_1, 1]), name='Bias_hidden')
                variable_summaries(b)

            out_matmul = tf.matmul(W, input, name='Matmul')
            out = tf.add(out_matmul, b, name='Add')
            tf.summary.histogram('pre_activations', out)
            if out_layer == False:
                out = tf.nn.relu(out, name='Relu')
                tf.summary.histogram('post_activations', out)

        return out


    def _placeholders_full_images(self, n_features, n_actions):
        '''
        Creates placeholders. For image only features.
        :param n_features: (int)
        :param n_actions:  (int)
        :return: (tensor) (tensor) (tensor)
        '''

        X = tf.placeholder(dtype='float32', shape=[n_features, 1], name='X_train')
        y = tf.placeholder(dtype='float32', shape=[n_actions, 1], name='y_train')
        training = tf.placeholder(dtype=tf.bool, shape=())

        return X, y, training