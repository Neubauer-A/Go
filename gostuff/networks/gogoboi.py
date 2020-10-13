from tensorflow.keras.layers import *
from tensorflow.keras.models import Model

def ggb_model(input_shape=(19,19,9), blocks=16):
    inputs = Input(shape=input_shape)
    first_conv = conv_block(kernel_size=1)(inputs)
    stack = block_stack(blocks=blocks)(first_conv)
    head = head()(stack)          
    return Model(inputs=inputs, outputs=head)

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
        return add([inputs, res])
    return f


def block_stack(blocks):
    def f(inputs):
        x = inputs
        for i in range(blocks):
            x = residual_block(block_num=i)(x)
        return x
    return f

def head():
    def f(inputs):
        conv = Conv2D(filters=361, kernel_size=(3,3), padding='same')(inputs)
        act = LeakyReLU()(conv)
        gap = GlobalAveragePooling2D()(act)
        return Activation("softmax")(gap)
    return f
