#ifndef MANUALCNN_H_
#define MANUALCNN_H_

#include <Eigen/Core>

#include "Config.h"

#include "RNG.h"

#include "Layer.h"
#include "Layer/FullyConnected.h"
#include "Layer/Convolutional.h"
#include "Layer/MaxPooling.h"

#include "Activation/ReLU.h"
#include "Activation/Identity.h"
#include "Activation/Sigmoid.h"
#include "Activation/Softmax.h"

#include "Output.h"
#include "Output/RegressionMSE.h"
#include "Output/BinaryClassEntropy.h"
#include "Output/MultiClassEntropy.h"

#include "Optimizer.h"
#include "Optimizer/SGD.h"
#include "Optimizer/AdaGrad.h"
#include "Optimizer/RMSProp.h"

#include "Callback.h"
#include "Callback/VerboseCallback.h"

#include "Network.h"

#endif /* MANUALCNN_H_ */
