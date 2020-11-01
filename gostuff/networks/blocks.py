from tensorflow.keras.layers import *

def multikernel_block(filters=64, activation=True):
    def f(inputs):
        # projections
        one = Conv2D(filters, 1)(inputs)
        three = Conv2D(filters, 1, padding='same')(inputs)
        five = Conv2D(filters, 1, padding='same')(inputs)
        seven = Conv2D(filters, 1, padding='same')(inputs)
        nine = Conv2D(filters, 1, padding='same')(inputs)
        # convolutions
        three = Conv2D(filters, (1,3), padding='same')(three)
        three = Conv2D(filters, (3,1), padding='same')(three)
        five = Conv2D(filters, (1,5), padding='same')(five)
        five = Conv2D(filters, (5,1), padding='same')(five)
        seven = Conv2D(filters, (1,7), padding='same')(seven)
        seven = Conv2D(filters, (7,1), padding='same')(seven)
        nine = Conv2D(filters, (1,9), padding='same')(nine)
        nine = Conv2D(filters, (9,1), padding='same')(nine)
        concat = Concatenate()([one, three, five, seven, nine])
        batch_norm = BatchNormalization()(concat)
        return LeakyReLU()(batch_norm) if activation else batch_norm
    return f

def multikernel_res_block(filters=64):
    def f(inputs):
        x = multikernel_block(filters)(inputs)
        x = multikernel_block(filters, activation=False)(x)
        x = Add()([inputs, x])
        return LeakyReLU()(x)
    return f

def multikernel_res_stack(blocks, filters=64):
    def f(inputs):
        x = inputs
        for i in range(blocks):
            x = multikernel_res_block(filters=filters)(x)
        return x
    return f

def conv_block(activation=True, filters=64, kernel_size=(3,3), padding="same", init="he_normal"):
    def f(inputs):
        conv = Conv2D(filters=filters, 
                      kernel_size=kernel_size,
                      padding=padding,
                      kernel_initializer=init)(inputs)
        batch_norm = BatchNormalization()(conv)
        return LeakyReLU()(batch_norm) if activation else batch_norm
    return f    

def residual_block(block_num):
    def f(inputs):
        res = conv_block(activation=True)(inputs)
        res = conv_block(activation=False)(res)
        add = add([inputs, res])
        return LeakyReLU()(add)
    return f

def res_stack(blocks):
    def f(inputs):
        x = inputs
        for i in range(blocks):
            x = residual_block(block_num=i)(x)
        return x
    return f

def gap_head(filters):
    def f(inputs):
        conv = Conv2D(filters=filters, kernel_size=3, padding='same')(inputs)
        gap = GlobalAveragePooling2D()(conv)
        return Activation("softmax")(gap)
    return f
