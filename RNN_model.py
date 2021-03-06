import tensorflow as tf


class RNNModel():
    def __init__(self, rnn_config):

        self.config = rnn_config
        self.reuse = rnn_config['mode'] == 'validate_RNN'
        self.embedding_dim = rnn_config['embedding_dim']
        #self.sequence_length = rnn_config['sequence_length']
        self.hidden_size = rnn_config['hidden_size']
        self.vocab_size = rnn_config['vocab_size']
        # Isnt't this missing a dimension?
        self.input_x = tf.placeholder(dtype=tf.int64, shape=[None, None], name="input_x") #self.sequence_length], name="input_x")
        self.input_y = tf.placeholder(dtype=tf.int64, shape=[None, None], name="input_y")#self.sequence_length], name="input_y")
        self.sequence_length_list = tf.placeholder(dtype=tf.int32, shape=[None,],name='sequence_length_list')
        self.batch_size = tf.shape(self.input_x)[0]  # dynamic size#rnn_config['batch_size']
        self.max_seq_length = tf.shape(self.input_x)[1]  # dynamic size
        self.sequence_mask = tf.sequence_mask(self.sequence_length_list, None, dtype=tf.float32)



        with tf.variable_scope("rnn", reuse=self.reuse):
            self.word_embeddings = tf.get_variable("word_embeddings", [self.vocab_size, self.embedding_dim])
            self.embedded_tokens = tf.nn.embedding_lookup(self.word_embeddings, self.input_x)

            # split by the timestamp #
            # rnncell = tf.nn.rnn_cell.BasicRNNCell(num_units=self.hidden_size)
            if rnn_config['is_add_layer']:
                rnncell = tf.nn.rnn_cell.LSTMCell(num_units=2*self.hidden_size)
                W_middle = tf.get_variable("W_middle", shape=[2 * self.hidden_size, self.hidden_size],
                                           initializer=tf.contrib.layers.xavier_initializer())
            else:
                rnncell = tf.nn.rnn_cell.LSTMCell(num_units=self.hidden_size)
            # dropout
            #if rnn_config['mode'] == 'train_RNN':
            #    rnncell = tf.contrib.rnn.DropoutWrapper(rnncell, output_keep_prob=0.5)
            state = rnncell.zero_state(batch_size=self.batch_size, dtype=tf.float32)
            outputs, state = tf.nn.dynamic_rnn(rnncell, self.embedded_tokens, sequence_length=self.sequence_length_list,
                                               initial_state=state)

            if rnn_config['is_add_layer']:
                outputs = tf.reshape(outputs,[-1,2*self.hidden_size])
                self.outputs = tf.matmul(outputs,W_middle)
            else:
                self.outputs = tf.reshape(outputs,[-1,self.hidden_size])  # shape: (batch_size*time_step, self.hidden_size)
            self.W_out = tf.get_variable("W_out", shape=[self.hidden_size, self.vocab_size],
                                         initializer=tf.contrib.layers.xavier_initializer())
            self.b_out = tf.Variable(tf.constant(0.1, shape=[self.vocab_size,]), name='b_out')

            # dropout
            if rnn_config['mode'] == 'train_RNN' and 'is_dropout' in rnn_config.keys():
                if rnn_config['is_dropout']:
                    self.outputs = tf.nn.dropout(self.outputs, keep_prob=0.4)
                    print('adding dropout after LSTM layer')

            logits = tf.nn.xw_plus_b(self.outputs, self.W_out, self.b_out)
            logits = tf.reshape(logits, shape=[self.max_seq_length, -1, self.vocab_size])  # (time_step,batch_size,vocab_size)
            self.logits = tf.transpose(logits, perm=[1, 0, 2])
            self.prediction = tf.argmax(logits, 1, name='prediction')
            self.loss = tf.contrib.seq2seq.sequence_loss(
                self.logits,
                self.input_y,
                self.sequence_mask,
                average_across_timesteps=True,
                average_across_batch=False,name="loss")

            self.eva_perplexity = tf.exp(self.loss, name="eva_perplexity")
            self.minimize_loss = tf.reduce_mean(self.loss,name="minize_loss")
            self.print_perplexity = tf.reduce_mean(self.eva_perplexity, name="print_perplexity")

            self.word_probabs = tf.exp(- tf.contrib.seq2seq.sequence_loss(
                self.logits,
                self.input_y,
                self.sequence_mask,
                average_across_timesteps=False,
                average_across_batch=False,name="word_prob"))
            self.sequence_probab = 1. / self.eva_perplexity

            self.log_sequence_probab = -self.loss
            self.log_word_probabs =- tf.contrib.seq2seq.sequence_loss(
                self.logits,
                self.input_y,
                self.sequence_mask,
                average_across_timesteps=False,
                average_across_batch=False,name="log_word_prob")



    def get_feed_dict_train(self, batch, which_sentences=None):
        '''batch --> feed_dict for training'''
        if which_sentences is None:
            which_sentences = range(batch.num_sentences)
        X, Y, batch_seq_lengths = batch.get_padded_data(which_sentences=which_sentences)
        feed_dict = {self.input_x: X,
                     self.input_y: Y,
                     self.sequence_length_list: batch_seq_lengths}
        return feed_dict


    def get_feed_dict_infer(self, batch, which_sentences=None):
        '''batch --> feed_dict for training'''
        if which_sentences is None:
            which_sentences = range(batch.num_sentences)
        X, _, batch_seq_lengths = batch.get_padded_data(which_sentences=which_sentences,
                                                        use_next_step_as_target=False, pad_target=False)
        feed_dict = {self.input_x: X,
                     self.sequence_length_list: batch_seq_lengths}
        return feed_dict


