# Copyright (c) MONAI Consortium
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest

import numpy as np
import torch
from parameterized import parameterized

from monai.config import USE_COMPILED
from monai.data.meta_obj import set_track_meta
from monai.data.meta_tensor import MetaTensor
from monai.data.utils import to_affine_nd
from monai.transforms import SpatialResample
from tests.utils import TEST_DEVICES, TEST_NDARRAYS_ALL, assert_allclose

TESTS = []


destinations_3d = [
    torch.tensor([[1.0, 0.0, 0.0, 0.0], [0.0, -1.0, 0.0, 1.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]),
    torch.tensor([[-1.0, 0.0, 0.0, 1.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]),
]
expected_3d = [
    torch.tensor([[[[4.0, 5.0, 6.0], [1.0, 2.0, 3.0]], [[10.0, 11.0, 12.0], [7.0, 8.0, 9.0]]]]),
    torch.tensor([[[[7.0, 8.0, 9.0], [10.0, 11.0, 12.0]], [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]]]),
]

for dst, expct in zip(destinations_3d, expected_3d):
    for device in TEST_DEVICES:
        for align in (False, True):
            interp = ("nearest", "bilinear", 0, 1) if align and USE_COMPILED else ("nearest", "bilinear")
            for interp_mode in interp:
                for padding_mode in ("zeros", "border", "reflection"):
                    TESTS.append(
                        [
                            torch.arange(12).reshape((1, 2, 2, 3)) + 1.0,  # data
                            *device,
                            {
                                "dst_affine": dst,
                                "dtype": torch.float64,
                                "align_corners": align,
                                "mode": interp_mode,
                                "padding_mode": padding_mode,
                            },
                            expct,
                        ]
                    )


destinations_2d = [
    torch.tensor([[1.0, 0.0, 0.0], [0.0, -1.0, 1.0], [0.0, 0.0, 1.0]]),  # flip the second
    torch.tensor([[-1.0, 0.0, 1.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),  # flip the first
]
expected_2d = [torch.tensor([[[2.0, 1.0], [4.0, 3.0]]]), torch.tensor([[[3.0, 4.0], [1.0, 2.0]]])]

for dst, expct in zip(destinations_2d, expected_2d):
    for device in TEST_DEVICES:
        for align in (False, True):
            for interp_mode in ("nearest", "bilinear"):
                TESTS.append(
                    [
                        torch.arange(4).reshape((1, 2, 2)) + 1.0,
                        *device,
                        {
                            "dst_affine": dst,
                            "dtype": torch.float32,
                            "align_corners": align,
                            "mode": interp_mode,
                            "padding_mode": "zeros",
                        },
                        expct,
                    ]
                )

TEST_4_5_D = []
for device in TEST_DEVICES:
    for dtype in (torch.float32, torch.float64):
        # 4D
        TEST_4_5_D.append(
            [
                (1, 2, 2, 3, 1),
                (1, 1, 1, 1, 2),
                *device,
                dtype,
                torch.tensor(
                    [
                        [[[0.5, 0.0], [0.0, 2.0], [1.5, 1.0]], [[3.5, 3.0], [3.0, 5.0], [4.5, 4.0]]],
                        [[[6.5, 6.0], [6.0, 8.0], [7.5, 7.0]], [[9.5, 9.0], [9.0, 11.0], [10.5, 10.0]]],
                    ]
                ),
            ]
        )
        # 5D
        TEST_4_5_D.append(
            [
                (1, 2, 2, 3, 1, 1),
                (1, 1, 1, 1, 2, 2),
                *device,
                dtype,
                torch.tensor(
                    [
                        [
                            [[[0.0, 0.0], [0.0, 1.0]], [[0.5, 0.0], [1.5, 1.0]], [[1.0, 2.0], [2.0, 2.0]]],
                            [[[3.0, 3.0], [3.0, 4.0]], [[3.5, 3.0], [4.5, 4.0]], [[4.0, 5.0], [5.0, 5.0]]],
                        ],
                        [
                            [[[6.0, 6.0], [6.0, 7.0]], [[6.5, 6.0], [7.5, 7.0]], [[7.0, 8.0], [8.0, 8.0]]],
                            [[[9.0, 9.0], [9.0, 10.0]], [[9.5, 9.0], [10.5, 10.0]], [[10.0, 11.0], [11.0, 11.0]]],
                        ],
                    ]
                ),
            ]
        )

TEST_TORCH_INPUT = []
for track_meta in (True,):
    for t in TEST_4_5_D:
        TEST_TORCH_INPUT.append(t + [track_meta])


class TestSpatialResample(unittest.TestCase):
    @parameterized.expand(TESTS)
    def test_flips(self, img, device, data_param, expected_output):
        for p in TEST_NDARRAYS_ALL:
            img = p(img)
            if isinstance(img, MetaTensor):
                img.affine = torch.eye(4)
            if hasattr(img, "to"):
                img = img.to(device)
            out = SpatialResample()(img=img, **data_param)
            assert_allclose(out, expected_output, rtol=1e-2, atol=1e-2)
            assert_allclose(out.affine, data_param["dst_affine"])

    @parameterized.expand(TEST_4_5_D)
    def test_4d_5d(self, new_shape, tile, device, dtype, expected_data):
        img = np.arange(12).reshape(new_shape)
        img = np.tile(img, tile)
        img = MetaTensor(img).to(device)

        dst = torch.tensor([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, -1.0, 1.5], [0.0, 0.0, 0.0, 1.0]])
        dst = dst.to(dtype)
        out = SpatialResample(dtype=dtype)(img=img, dst_affine=dst)
        assert_allclose(out, expected_data[None], rtol=1e-2, atol=1e-2)
        assert_allclose(out.affine, dst.to(torch.float32), rtol=1e-2, atol=1e-2)

    @parameterized.expand(TEST_DEVICES)
    def test_ill_affine(self, device):
        img = MetaTensor(torch.arange(12).reshape(1, 2, 2, 3)).to(device)
        ill_affine = torch.tensor([[1, 0, 0, 0], [0, 0, 0, 0], [0, 0, -1, 1.5], [0, 0, 0, 1]])
        with self.assertRaises(ValueError):
            img.affine = torch.eye(4)
            dst_affine = ill_affine
            SpatialResample()(img=img, dst_affine=dst_affine)
        with self.assertRaises(ValueError):
            img.affine = ill_affine
            dst_affine = torch.eye(4)
            SpatialResample()(img=img, dst_affine=dst_affine)
        with self.assertRaises(ValueError):
            img.affine = torch.eye(4)
            dst_affine = torch.eye(4) * 0.1
            SpatialResample(mode=None)(img=img, dst_affine=dst_affine)

    @parameterized.expand(TEST_TORCH_INPUT)
    def test_input_torch(self, new_shape, tile, device, dtype, expected_data, track_meta):
        set_track_meta(track_meta)
        img = np.arange(12).reshape(new_shape)
        img = torch.as_tensor(np.tile(img, tile)).to(device)
        dst = torch.tensor([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, -1.0, 1.5], [0.0, 0.0, 0.0, 1.0]])
        dst = dst.to(dtype).to(device)

        out = SpatialResample(dtype=dtype)(img=img, dst_affine=dst)
        assert_allclose(out, expected_data[None], rtol=1e-2, atol=1e-2)
        if track_meta:
            self.assertIsInstance(out, MetaTensor)
            assert_allclose(out.affine, dst.to(torch.float32), rtol=1e-2, atol=1e-2)
        else:
            self.assertIsInstance(out, torch.Tensor)
            self.assertNotIsInstance(out, MetaTensor)

    @parameterized.expand(TESTS)
    def test_inverse(self, img, device, data_param, expected_output):
        img = MetaTensor(img, affine=torch.eye(4)).to(device)
        tr = SpatialResample()
        out = tr(img=img, **data_param)
        assert_allclose(out, expected_output, rtol=1e-2, atol=1e-2)
        assert_allclose(out.affine, data_param["dst_affine"])

        # inverse
        out = tr.inverse(out)
        assert_allclose(img, out)
        expected_affine = to_affine_nd(len(out.affine) - 1, torch.eye(4))
        assert_allclose(out.affine, expected_affine)


if __name__ == "__main__":
    unittest.main()