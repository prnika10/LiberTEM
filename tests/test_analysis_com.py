import pytest
import numpy as np
from scipy.ndimage import measurements
from libertem import masks
from libertem.io.dataset.memory import MemoryDataSet

from utils import _mk_random


@pytest.fixture
def ds_w_zero_frame():
    data = _mk_random(size=(16, 16, 16, 16))
    data[0, 0] = np.zeros((16, 16))
    dataset = MemoryDataSet(
        data=data.astype("<u2"),
        tileshape=(1, 16, 16),
        num_partitions=2,
        sig_dims=2,
    )
    return dataset


@pytest.fixture
def ds_random():
    data = _mk_random(size=(16, 16, 16, 16))
    dataset = MemoryDataSet(
        data=data.astype("<u2"),
        tileshape=(1, 16, 16),
        num_partitions=2,
    )
    return dataset


@pytest.mark.parametrize(
    'TYPE', ['JOB', 'UDF']
)
def test_com_with_zero_frames(ds_w_zero_frame, lt_ctx, TYPE):
    analysis = lt_ctx.create_com_analysis(
        dataset=ds_w_zero_frame, cx=0, cy=0, mask_radius=0
    )
    analysis.TYPE = TYPE
    results = lt_ctx.run(analysis)

    # no inf/nan in center_x and center_y
    assert not np.any(np.isinf(results[3].raw_data))
    assert not np.any(np.isinf(results[4].raw_data))
    assert not np.any(np.isnan(results[3].raw_data))
    assert not np.any(np.isnan(results[4].raw_data))

    # no inf/nan in divergence/magnitude
    assert not np.any(np.isinf(results[1].raw_data))
    assert not np.any(np.isinf(results[2].raw_data))
    assert not np.any(np.isnan(results[1].raw_data))
    assert not np.any(np.isnan(results[2].raw_data))


@pytest.mark.parametrize(
    'TYPE', ['JOB', 'UDF']
)
def test_com_comparison_scipy_1_nomask(ds_random, lt_ctx, TYPE):
    analysis = lt_ctx.create_com_analysis(
        dataset=ds_random, cx=0, cy=0, mask_radius=None
    )
    analysis.TYPE = TYPE
    results = lt_ctx.run(analysis)
    raw_data_by_frame = ds_random.data.reshape((16 * 16, 16, 16))
    field_x, field_y = results.field.raw_data
    field_x = field_x.reshape((16 * 16))
    field_y = field_y.reshape((16 * 16))
    for idx in range(16 * 16):
        scy, scx = measurements.center_of_mass(raw_data_by_frame[idx])
        assert np.allclose(scx, field_x[idx])
        assert np.allclose(scy, field_y[idx])


@pytest.mark.parametrize(
    'TYPE', ['JOB', 'UDF']
)
def test_com_comparison_scipy_2_masked(ds_random, lt_ctx, TYPE):
    analysis = lt_ctx.create_com_analysis(
        dataset=ds_random, cx=0, cy=0, mask_radius=8
    )
    analysis.TYPE = TYPE
    results = lt_ctx.run(analysis)
    raw_data_by_frame = ds_random.data.reshape((16 * 16, 16, 16))
    field_x, field_y = results.field.raw_data
    field_x = field_x.reshape((16 * 16))
    field_y = field_y.reshape((16 * 16))
    disk_mask = masks.circular(
        centerX=0, centerY=0,
        imageSizeX=16,
        imageSizeY=16,
        radius=8,
    )
    for idx in range(16 * 16):
        masked_frame = raw_data_by_frame[idx] * disk_mask
        scy, scx = measurements.center_of_mass(masked_frame)
        assert np.allclose(scx, field_x[idx])
        assert np.allclose(scy, field_y[idx])


def test_com_fails_with_non_4d_data_1(lt_ctx):
    data = _mk_random(size=(16 * 16, 16, 16))
    dataset = MemoryDataSet(
        data=data.astype("<u2"),
        tileshape=(1, 16, 16),
        num_partitions=32,
    )
    with pytest.raises(Exception):
        lt_ctx.create_com_analysis(
            dataset=dataset, cx=0, cy=0, mask_radius=8
        )


def test_com_fails_with_non_4d_data_2(lt_ctx):
    data = _mk_random(size=(16, 16, 16 * 16))
    dataset = MemoryDataSet(
        data=data.astype("<u2"),
        tileshape=(1, 16 * 16),
        num_partitions=16,
        sig_dims=1,
    )
    with pytest.raises(Exception):
        lt_ctx.create_com_analysis(
            dataset=dataset, cx=0, cy=0, mask_radius=8
        )


@pytest.mark.parametrize(
    'TYPE', ['JOB', 'UDF']
)
def test_com_complex_numbers(lt_ctx, TYPE):
    data = _mk_random(size=(16, 16, 16, 16), dtype="complex64")
    ds_complex = MemoryDataSet(
        data=data,
        tileshape=(1, 16, 16),
        num_partitions=2,
    )
    analysis = lt_ctx.create_com_analysis(dataset=ds_complex, cx=0, cy=0, mask_radius=None)
    analysis.TYPE = TYPE
    results = lt_ctx.run(analysis)

    reshaped_data = ds_complex.data.reshape((16 * 16, 16, 16))
    field_x = results.x_real.raw_data + 1j * results.x_imag.raw_data
    field_y = results.y_real.raw_data + 1j * results.y_imag.raw_data

    field_x = field_x.reshape((16 * 16))
    field_y = field_y.reshape((16 * 16))
    for idx in range(16 * 16):
        scy, scx = measurements.center_of_mass(reshaped_data[idx])

        print(scx, field_x[idx])

        # difference between scipy and our impl: we don't divide by zero
        if np.isinf(scx):
            assert field_x[idx] == 0
            assert field_y[idx] == 0
        else:
            assert np.allclose(scx, field_x[idx])
            assert np.allclose(scy, field_y[idx])


@pytest.mark.parametrize(
    'TYPE', ['JOB', 'UDF']
)
def test_com_complex_numbers_handcrafted_1(lt_ctx, TYPE):
    data = np.ones((3, 3, 4, 4), dtype="complex64")
    data[0, 0] = np.array([
        [0,    0,    0, 0],
        [0, 1+2j, 1-2j, 0],
        [0, 1-2j, 1+2j, 0],
        [0,    0,    0, 0],
    ])
    ds_complex = MemoryDataSet(
        data=data,
        tileshape=(1, 4, 4),
        num_partitions=9,
    )
    analysis = lt_ctx.create_com_analysis(dataset=ds_complex, cx=0, cy=0, mask_radius=None)
    analysis.TYPE = TYPE
    results = lt_ctx.run(analysis)

    field_x = results.x_real.raw_data + 1j * results.x_imag.raw_data
    field_y = results.y_real.raw_data + 1j * results.y_imag.raw_data

    assert field_x[0, 0] == 1.5
    assert field_y[0, 0] == 1.5


@pytest.mark.parametrize(
    'TYPE', ['JOB', 'UDF']
)
def test_com_complex_numbers_handcrafted_2(lt_ctx, TYPE):
    data = np.ones((3, 3, 4, 4), dtype="complex64")
    data[0, 0] = np.array([
        [0,    0,    0, 0],
        [0,    0, 1-2j, 0],
        [0, 1-2j,    0, 0],
        [0,    0,    0, 0],
    ])
    ds_complex = MemoryDataSet(
        data=data,
        tileshape=(1, 4, 4),
        num_partitions=9,
    )
    analysis = lt_ctx.create_com_analysis(dataset=ds_complex, cx=0, cy=0, mask_radius=None)
    analysis.TYPE = TYPE
    results = lt_ctx.run(analysis)

    field_x = results.x_real.raw_data + 1j * results.x_imag.raw_data
    field_y = results.y_real.raw_data + 1j * results.y_imag.raw_data

    assert field_x[0, 0] == 1.5
    assert field_y[0, 0] == 1.5


@pytest.mark.parametrize(
    'TYPE', ['JOB', 'UDF']
)
def test_com_complex_numbers_handcrafted_3(lt_ctx, TYPE):
    data = np.ones((3, 3, 4, 4), dtype="complex64")
    data[0, 0] = np.array([
        0,    0,    0, 0,
        0,    0, 1-2j, 0,
        0,    0,    0, 0,
        0,    0,    0, 0,
    ], dtype="complex64").reshape((4, 4))
    ds_complex = MemoryDataSet(
        data=data,
        tileshape=(1, 4, 4),
        num_partitions=9,
    )
    analysis = lt_ctx.create_com_analysis(dataset=ds_complex, cx=0, cy=0, mask_radius=None)
    analysis.TYPE = TYPE
    results = lt_ctx.run(analysis)

    print(data[0, 0])

    field_x = results.x_real.raw_data + 1j * results.x_imag.raw_data
    field_y = results.y_real.raw_data + 1j * results.y_imag.raw_data

    assert field_x[0, 0] == 2
    assert field_y[0, 0] == 1


@pytest.mark.parametrize(
    'TYPE', ['JOB', 'UDF']
)
def test_com_default_params(lt_ctx, TYPE):
    data = _mk_random(size=(16, 16, 16, 16))
    dataset = MemoryDataSet(
        data=data.astype("<u2"),
        tileshape=(1, 16, 16),
        num_partitions=16,
        sig_dims=2,
    )
    analysis = lt_ctx.create_com_analysis(
        dataset=dataset,
    )
    analysis.TYPE = TYPE
    lt_ctx.run(analysis)


@pytest.mark.parametrize(
    'TYPE', ['JOB', 'UDF']
)
def test_com_divergence(lt_ctx, TYPE):
    data = np.zeros((3, 3, 3, 3), dtype=np.float32)
    for i in range(3):
        for j in range(3):
            data[i, j, i, j] = 1
    dataset = MemoryDataSet(
        data=data,
        sig_dims=2,
    )
    analysis = lt_ctx.create_com_analysis(
        dataset=dataset,
        cy=1,
        cx=1,

    )
    analysis.TYPE = TYPE
    res = lt_ctx.run(analysis)

    print(data)
    print("y", res["y"].raw_data)
    print("x", res["x"].raw_data)
    print("divergence", res["divergence"].raw_data)
    print("curl", res["curl"].raw_data)
    assert np.all(res["x"].raw_data == [[-1, 0, 1], [-1, 0, 1], [-1, 0, 1]])
    assert np.all(res["y"].raw_data == [[-1, -1, -1], [0, 0, 0], [1, 1, 1]])

    assert np.all(res["divergence"].raw_data == 2)
    assert np.all(res["curl"].raw_data == 0)


@pytest.mark.parametrize(
    'TYPE', ['JOB', 'UDF']
)
def test_com_divergence_2(lt_ctx, TYPE):
    data = np.zeros((3, 3, 3, 3), dtype=np.float32)
    for i in range(3):
        for j in range(3):
            data[i, j, 2-i, 2-j] = 1
    dataset = MemoryDataSet(
        data=data,
        sig_dims=2,
    )
    analysis = lt_ctx.create_com_analysis(
        dataset=dataset,
        cy=1,
        cx=1,
    )
    analysis.TYPE = TYPE
    res = lt_ctx.run(analysis)

    print(data)
    print("y", res["y"].raw_data)
    print("x", res["x"].raw_data)
    print("divergence", res["divergence"].raw_data)
    print("curl", res["curl"].raw_data)
    assert np.all(res["x"].raw_data == [[1, 0, -1], [1, 0, -1], [1, 0, -1]])
    assert np.all(res["y"].raw_data == [[1, 1, 1], [0, 0, 0], [-1, -1, -1]])

    assert np.all(res["divergence"].raw_data == -2)
    assert np.all(res["curl"].raw_data == 0)


@pytest.mark.parametrize(
    'TYPE', ['JOB', 'UDF']
)
def test_com_curl(lt_ctx, TYPE):
    data = np.zeros((3, 3, 3, 3), dtype=np.float32)
    for y in range(3):
        for x in range(3):
            data[y, x, x, 2-y] = 1
    dataset = MemoryDataSet(
        data=data,
        sig_dims=2,
    )
    analysis = lt_ctx.create_com_analysis(
        dataset=dataset,
        cy=1,
        cx=1
    )
    analysis.TYPE = TYPE
    res = lt_ctx.run(analysis)

    print(data)
    print("y", res["y"].raw_data)
    print("x", res["x"].raw_data)
    print("divergence", res["divergence"].raw_data)
    print("curl", res["curl"].raw_data)

    assert np.all(res["x"].raw_data == [[1, 1, 1], [0, 0, 0], [-1, -1, -1]])
    assert np.all(res["y"].raw_data == [[-1, 0, 1], [-1, 0, 1], [-1, 0, 1]])

    assert np.all(res["divergence"].raw_data == 0)
    # Data "rotating to the right"
    # Y points down, x points right, right-handed coordinate system: z points away
    # Right handed coordinate system: The result should be positive
    # since the patterns are rotated in positive direction
    # https://commons.wikimedia.org/wiki/File:Right_hand_rule_simple.png
    assert np.all(res["curl"].raw_data == 2)


@pytest.mark.parametrize(
    'TYPE', ['JOB', 'UDF']
)
def test_com_curl_2(lt_ctx, TYPE):
    data = np.zeros((3, 3, 3, 3), dtype=np.float32)
    for y in range(3):
        for x in range(3):
            data[y, x, 2-x, y] = 1
    dataset = MemoryDataSet(
        data=data,
        sig_dims=2,
    )
    analysis = lt_ctx.create_com_analysis(
        dataset=dataset,
        cy=1,
        cx=1
    )
    analysis.TYPE = TYPE
    res = lt_ctx.run(analysis)

    print(data)
    print("y", res["y"].raw_data)
    print("x", res["x"].raw_data)
    print("divergence", res["divergence"].raw_data)
    print("curl", res["curl"].raw_data)

    assert np.all(res["x"].raw_data == [[-1, -1, -1], [0, 0, 0], [1, 1, 1]])
    assert np.all(res["y"].raw_data == [[1, 0, -1], [1, 0, -1], [1, 0, -1]])

    assert np.all(res["divergence"].raw_data == 0)
    assert np.all(res["curl"].raw_data == -2)


@pytest.mark.parametrize(
    'TYPE', ['JOB', 'UDF']
)
def test_com_curl_flip(lt_ctx, TYPE):
    data = np.zeros((3, 3, 3, 3), dtype=np.float32)
    for y in range(3):
        for x in range(3):
            data[y, x, 2-x, y] = 1
    data_flipped = np.flip(data, axis=2)
    dataset = MemoryDataSet(
        data=data_flipped,
        sig_dims=2,
    )
    analysis = lt_ctx.create_com_analysis(
        dataset=dataset,
        cy=1,
        cx=1,
        flip_y=True
    )
    analysis.TYPE = TYPE
    res = lt_ctx.run(analysis)

    print("data", data)
    print("flipped", data_flipped)
    print("y", res["y"].raw_data)
    print("x", res["x"].raw_data)
    print("divergence", res["divergence"].raw_data)
    print("curl", res["curl"].raw_data)

    assert np.all(res["x"].raw_data == [[-1, -1, -1], [0, 0, 0], [1, 1, 1]])
    assert np.all(res["y"].raw_data == [[1, 0, -1], [1, 0, -1], [1, 0, -1]])

    assert np.all(res["divergence"].raw_data == 0)
    assert np.all(res["curl"].raw_data == -2)

@pytest.mark.parametrize(
    'TYPE', ['JOB', 'UDF']
)
def test_com_curl_rotate(lt_ctx, TYPE):
    data = np.zeros((3, 3, 3, 3), dtype=np.float32)
    for y in range(3):
        for x in range(3):
            data[y, x, 2-x, y] = 1
    # Rotate 90 degrees clockwise
    data_90deg = np.zeros_like(data)
    for y in range(3):
        for x in range(3):
            data_90deg[:, :, x, 2-y] = data[:, :, y, x]
    dataset = MemoryDataSet(
        data=data_90deg,
        sig_dims=2,
    )
    analysis = lt_ctx.create_com_analysis(
        dataset=dataset,
        cy=1,
        cx=1,
        scan_rotation=-90.
    )
    analysis.TYPE = TYPE
    res = lt_ctx.run(analysis)

    print("data", data)
    print("data_90deg", data_90deg)
    print("y", res["y"].raw_data)
    print("x", res["x"].raw_data)
    print("divergence", res["divergence"].raw_data)
    print("curl", res["curl"].raw_data)

    assert np.allclose(res["x"].raw_data, [[-1, -1, -1], [0, 0, 0], [1, 1, 1]])
    assert np.allclose(res["y"].raw_data, [[1, 0, -1], [1, 0, -1], [1, 0, -1]])

    assert np.allclose(res["divergence"].raw_data, 0)
    assert np.allclose(res["curl"].raw_data, -2)
