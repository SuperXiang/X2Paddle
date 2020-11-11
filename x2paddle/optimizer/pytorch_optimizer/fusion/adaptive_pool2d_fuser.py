#   Copyright (c) 2020  PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np
from x2paddle.optimizer.pytorch_optimizer.pattern_matcher import FuseBase
from x2paddle.core.program import PaddleGraph, PaddleLayer
from x2paddle.core.util import *


class AdaptivePool2dFuser(FuseBase):
    def __init__(self):
        super(AdaptivePool2dFuser, self).__init__(graph_type="dygraph")

    def build_pattern(self):
        """ 描述需要替换的adaptive pool2d图结构。
        adaptive pool2d层模式python实现代码示例:
            x68 = fluid.layers.shape(input=x60)
            x69 = len(x68)
            x70 = x69 <= 2
            if x70 :
                raise RaiseException('Exception')
            x73 = []
            x74 = x68[-2: 2147483647: 1]
            x75 = len(x74)
            x76 = [2, x75]
            x77 = min(x76)
            for _x79 in range(x77):
                x80 = [6, 6][_x79]
                x73.append(x80)
            x81 = fluid.layers.adaptive_pool2d(input=x60, pool_size=x73, pool_type='avg')
        """

        def gen_name(id):
            return "x" + str(id)

        self.pattern.add_layer(
            "fluid.layers.shape",
            inputs={'input': "pool-input-0"},
            outputs=[gen_name(1)])
        self.pattern.add_layer(
            "prim.len", inputs={"input": gen_name(1)}, outputs=[gen_name(6)])
        self.pattern.add_layer(
            "prim.le", inputs={"x": gen_name(6)}, outputs=[gen_name(8)], y=2)
        self.pattern.add_layer("prim.if", {'input': gen_name(8)}, [gen_name(9)])
        if_layer = self.pattern.layers[list(self.pattern.layers.keys())[-1]]
        pattern_block0 = PaddleGraph(if_layer, graph_type="dygraph")
        pattern_block0.add_layer(
            "prim.exception",
            inputs={},
            outputs=[gen_name(9)],
            input="Exception")
        if_layer.add_block(pattern_block0)
        pattern_block1 = PaddleGraph(if_layer, graph_type="dygraph")
        if_layer.add_block(pattern_block1)
        self.pattern.add_layer("prim.list", inputs={}, outputs=[gen_name(10)])
        self.pattern.add_layer(
            "prim.slice",
            inputs={"input": gen_name(1), },
            outputs=[gen_name(12)],
            start=-1,
            end=100,
            step=1)
        self.pattern.add_layer(
            "prim.len", inputs={"input": gen_name(12)}, outputs=[gen_name(14)])
        self.pattern.add_layer(
            "prim.list",
            inputs={"input1": gen_name(14)},
            outputs=[gen_name(15)],
            input0=2)
        self.pattern.add_layer(
            "prim.min", inputs={"input": gen_name(15)}, outputs=[gen_name(16)])
        self.pattern.add_layer("prim.loop", {'input': gen_name(16)},
                               [gen_name(17), gen_name(18)])
        loop_layer = self.pattern.layers[list(self.pattern.layers.keys())[-1]]
        pattern_block = PaddleGraph(loop_layer, graph_type="dygraph")
        pattern_block.add_layer(
            "prim.getitem",
            inputs={"index": gen_name(18)},
            outputs=[gen_name(19)],
            list=[6, 6])
        pattern_block.add_layer(
            "prim.append",
            inputs={"list": gen_name(10),
                    "index": gen_name(19)},
            outputs=[gen_name(20)])
        loop_layer.inputs["input-0"] = gen_name(10)
        loop_layer.add_block(pattern_block)
        pool_attrs = {'pool_type': string("avg")}
        self.pattern.add_layer(
            "fluid.layers.adaptive_pool2d",
            inputs={'input': "pool-input-0",
                    "pool_size": gen_name(10)},
            outputs=[gen_name(21)],
            **pool_attrs)
        self.pattern.build(inputs={"input-0": "pool-input-0", })

    def insert_new_layer(self, graph, parameters, matches):
        parameters = graph.parameters
        new_layer = self.gen_new_layer(parameters, matches)
        new_layer_id = list(matches.keys())[0]
        graph.layers[new_layer_id] = new_layer
        matches.pop(new_layer_id)

    def gen_new_layer(self, parameters, matches):
        layers_id = list(matches.keys())
        layer = matches[layers_id[11]]
        pool_size = layer.attrs["list"]
        layer = matches[layers_id[0]]
        input_name = layer.inputs["input"]
        layer = matches[layers_id[-1]]
        output_name = layer.outputs[0]
        pool_type = layer.attrs["pool_type"]
        attrs = dict()
        attrs["pool_size"] = pool_size
        attrs["pool_type"] = pool_type
        new_layer = PaddleLayer(
            layers_id[0],
            "fluid.layers.adaptive_pool2d",
            inputs={"input": input_name},
            outputs=[output_name],
            **attrs)
        return new_layer
