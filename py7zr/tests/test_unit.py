import binascii
import io
import lzma
import os
import pytest
import py7zr.archiveinfo
import py7zr.compression
import py7zr.helpers
import py7zr.properties
import py7zr.io

testdata_path = os.path.join(os.path.dirname(__file__), 'data')


@pytest.mark.unit
def test_py7zr_signatureheader():
    header_data = io.BytesIO(b'\x37\x7a\xbc\xaf\x27\x1c\x00\x02\x70\x2a\xb7\x37\xa0\x00\x00\x00\x00\x00\x00\x00\x21'
                             b'\x00\x00\x00\x00\x00\x00\x00\xb9\xb8\xe4\xbf')
    header = py7zr.archiveinfo.SignatureHeader.retrieve(header_data)
    assert header is not None
    assert header.version == (0, 2)
    assert header.nextheaderofs == 160


@pytest.mark.unit
def test_py7zr_mainstreams():
    header_data = io.BytesIO(b'\x04\x06\x00\x01\t0\x00\x07\x0b\x01\x00\x01#\x03\x01\x01\x05]\x00\x00\x00\x02\x0cB\x00'
                             b'\x08\r\x02\t!\n\x01>jb\x08\xce\x9a\xb7\x88\x00\x00')
    pid = header_data.read(1)
    assert pid == py7zr.properties.Property.MAIN_STREAMS_INFO
    streams = py7zr.archiveinfo.StreamsInfo.retrieve(header_data)
    assert streams is not None


@pytest.mark.unit
def test_py7zr_folder_retrive():
    header_data = io.BytesIO(b'\x0b'
                             b'\x01\x00\x01#\x03\x01\x01\x05]\x00\x10\x00\x00')
    pid = header_data.read(1)
    assert pid == py7zr.properties.Property.FOLDER
    num_folders = py7zr.io.read_byte(header_data)
    assert num_folders == 1
    external = py7zr.io.read_byte(header_data)
    assert external == 0x00
    folder = py7zr.archiveinfo.Folder.retrieve(header_data)
    assert folder.packed_indices == [0]
    assert folder.totalin == 1
    assert folder.totalout == 1
    assert folder.digestdefined is False
    coder = folder.coders[0]
    assert coder['method'] == b'\x03\x01\x01'
    assert coder['properties'] == b']\x00\x10\x00\x00'
    assert coder['numinstreams'] == 1
    assert coder['numoutstreams'] == 1


@pytest.mark.unit
def test_py7zr_folder_write():
    folders = []
    for _ in range(1):
        folder = py7zr.archiveinfo.Folder()
        folder.bindpairs = []
        folder.coders = [{'method': b"\x03\x01\x01", 'numinstreams': 1,
                          'numoutstreams': 1, 'properties': b']\x00\x10\x00\x00'}]
        folder.crc = None
        folder.digestdefined = False
        folder.packed_indices = [0]
        folder.solid = True
        folder.totalin = 1
        folder.totalout = 1
        folders.append(folder)
    #
    buffer = io.BytesIO()
    # following should be run in StreamsInfo class.
    py7zr.io.write_byte(buffer, py7zr.properties.Property.FOLDER)
    py7zr.io.write_uint64(buffer, len(folders))
    external = b'\x00'
    py7zr.io.write_byte(buffer, external)
    for folder in folders:
        folder.write(buffer)
    actual = buffer.getvalue()
    assert actual == b'\x0b\x01\x00\x01#\x03\x01\x01\x05]\x00\x10\x00\x00'


@pytest.mark.unit
def test_py7zr_unpack_info():
    # prepare for unpack_info values
    unpack_info = py7zr.archiveinfo.UnpackInfo()
    unpack_info.folders = []
    for _ in range(1):
        folder = py7zr.archiveinfo.Folder()
        folder.bindpairs = []
        folder.coders = [{'method': b"\x03\x01\x01", 'numinstreams': 1,
                          'numoutstreams': 1, 'properties': b']\x00\x10\x00\x00'}]
        folder.crc = None
        folder.digestdefined = False
        folder.packed_indices = [0]
        folder.solid = True
        folder.totalin = 1
        folder.totalout = 1
        folder.unpacksizes = [0x22]
        unpack_info.folders.append(folder)
    unpack_info.numfolders = len(unpack_info.folders)
    #
    buffer = io.BytesIO()
    unpack_info.write(buffer)
    actual = buffer.getvalue()
    assert actual == b'\x07\x0b\x01\x00\x01#\x03\x01\x01\x05]\x00\x10\x00\x00\x0c\x22\x00'


@pytest.mark.unit
def test_py7zr_substreamsinfo():
    header_data = io.BytesIO(b'\x08\x0d\x03\x09\x6f\x3a\n\x01\xdb\xaej\xb3\x07\x8d\xbf\xdc\xber\xfc\x80\x00')
    pid = header_data.read(1)
    assert pid == py7zr.properties.Property.SUBSTREAMS_INFO
    folders = [py7zr.archiveinfo.Folder()]
    folders[0].unpacksizes = [728]
    numfolders = 1
    ss = py7zr.archiveinfo.SubstreamsInfo.retrieve(header_data, numfolders, folders)
    pos = header_data.tell()
    print(pos)
    assert ss.digestsdefined == [True, True, True]
    assert ss.digests[0] == 3010113243
    assert ss.digests[1] == 3703540999
    assert ss.digests[2] == 2164028094
    assert ss.num_unpackstreams_folders[0] == 3
    assert ss.unpacksizes == [111, 58, 559]


@pytest.mark.unit
def test_py7zr_substreamsinfo_write():
    folders = [py7zr.archiveinfo.Folder()]
    folders[0].unpacksizes = [728]
    ss = py7zr.archiveinfo.SubstreamsInfo()
    buffer = io.BytesIO()
    ss.digestsdefined = [True, True, True]
    ss.digests = [3010113243, 3703540999, 2164028094]
    ss.num_unpackstreams_folders = [3]
    ss.unpacksizes = [111, 58, 559]
    numfolders = len(folders)
    ss.write(buffer, numfolders)
    actual = buffer.getvalue()
    assert actual == b'\x08\x0d\x03\x09\x6f\x3a\n\x01\xdb\xaej\xb3\x07\x8d\xbf\xdc\xber\xfc\x80\x00'


@pytest.mark.unit
def test_py7zr_header():
    fp = open(os.path.join(testdata_path, 'solid.7z'), 'rb')
    header_data = io.BytesIO(b'\x01'
                             b'\x04\x06\x00\x01\t0\x00\x07\x0b\x01\x00\x01#\x03\x01\x01\x05]\x00\x00\x00\x02\x0cB\x00'
                             b'\x08\r\x02\t!\n\x01>jb\x08\xce\x9a\xb7\x88\x00\x00'
                             b'\x05\x03\x0e\x01\x80\x11=\x00t\x00e\x00s\x00t\x00\x00\x00t\x00e\x00s\x00t\x001\x00.'
                             b'\x00t\x00x\x00t\x00\x00\x00t\x00e\x00s\x00t\x00/\x00t\x00e\x00s\x00t\x002\x00.\x00t\x00x'
                             b'\x00t\x00\x00\x00\x14\x1a\x01\x00\x04>\xe6\x0f{H\xc6\x01d\xca \x8byH\xc6\x01\x8c\xfa\xb6'
                             b'\x83yH\xc6\x01\x15\x0e\x01\x00\x10\x00\x00\x00 \x00\x00\x00 \x00\x00\x00\x00\x00')
    header = py7zr.archiveinfo.Header.retrieve(fp, header_data, start_pos=32)
    assert header is not None
    assert header.files_info is not None
    assert header.main_streams is not None
    assert header.files_info.numfiles == 3
    assert len(header.files_info.files) == header.files_info.numfiles


@pytest.mark.unit
def test_py7zr_encoded_header():
    fp = open(os.path.join(testdata_path, 'test_5.7z'), 'rb')
    # set test data to buffer that start with Property.ENCODED_HEADER
    buffer = io.BytesIO(b'\x17\x060\x01\tp\x00\x07\x0b\x01\x00\x01#\x03\x01\x01\x05]\x00'
                        b'\x00\x10\x00\x0c\x80\x9d\n\x01\xe5\xa1\xb7b\x00\x00')
    header = py7zr.archiveinfo.Header.retrieve(fp, buffer, start_pos=32)
    assert header is not None
    assert header.files_info is not None
    assert header.main_streams is not None
    assert header.files_info.numfiles == 3
    assert len(header.files_info.files) == header.files_info.numfiles


@pytest.mark.unit
def test_py7zr_files_info_1():
    header_data = io.BytesIO(b'\x05\x03\x0e\x01\x80\x11=\x00t\x00e\x00s\x00t\x00\x00\x00t\x00e\x00s\x00t\x001\x00.'
                             b'\x00t\x00x\x00t\x00\x00\x00t\x00e\x00s\x00t\x00/\x00t\x00e\x00s\x00t\x002\x00.\x00t\x00x'
                             b'\x00t\x00\x00\x00\x14\x1a\x01\x00\x04>\xe6\x0f{H\xc6\x01d\xca \x8byH\xc6\x01\x8c\xfa\xb6'
                             b'\x83yH\xc6\x01\x15\x0e\x01\x00\x10\x00\x00\x00 \x00\x00\x00 \x00\x00\x00\x00\x00')
    pid = header_data.read(1)
    assert pid == py7zr.properties.Property.FILES_INFO
    files_info = py7zr.archiveinfo.FilesInfo.retrieve(header_data)
    assert files_info is not None
    assert files_info.files[0].get('filename') == 'test'
    assert files_info.files[1].get('filename') == 'test1.txt'
    assert files_info.files[2].get('filename') == 'test/test2.txt'


@pytest.mark.unit
def test_py7zr_files_info_2():
    header_data = io.BytesIO(b'\x05\x04\x11_\x00c\x00o\x00p\x00y\x00i\x00n\x00g\x00.\x00t\x00x\x00t\x00\x00\x00H\x00'
                             b'i\x00s\x00t\x00o\x00r\x00y\x00.\x00t\x00x\x00t\x00\x00\x00L\x00i\x00c\x00e\x00n\x00s'
                             b'\x00e\x00.\x00t\x00x\x00t\x00\x00\x00r\x00e\x00a\x00d\x00m\x00e\x00.\x00t\x00x\x00t\x00'
                             b'\x00\x00\x14"\x01\x00\x00[\x17\xe6\xc70\xc1\x01\x00Vh\xb5\xda\xf8\xc5\x01\x00\x97\xbd'
                             b'\xf9\x07\xf7\xc4\x01\x00gK\xa8\xda\xf8\xc5\x01\x15\x12\x01\x00  \x00\x00  \x00'
                             b'\x00  \x00\x00  \x00\x00\x00\x00')
    pid = header_data.read(1)
    assert pid == py7zr.properties.Property.FILES_INFO
    files_info = py7zr.archiveinfo.FilesInfo.retrieve(header_data)
    assert files_info is not None
    assert files_info.numfiles == 4
    assert files_info.files[0].get('filename') == 'copying.txt'
    assert files_info.files[0].get('attributes') == 0x2020
    assert files_info.files[1].get('filename') == 'History.txt'
    assert files_info.files[1].get('attributes') == 0x2020
    assert files_info.files[2].get('filename') == 'License.txt'
    assert files_info.files[2].get('attributes') == 0x2020
    assert files_info.files[3].get('filename') == 'readme.txt'
    assert files_info.files[3].get('attributes') == 0x2020


@pytest.mark.unit
def test_lzma_lzma2_compressor():
    filters = [{'id': 33, 'dict_size': 16777216}]
    assert lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters) is not None


@pytest.mark.unit
def test_lzma_lzma2bcj_compressor():
    filters = [{'id': 4}, {'id': 33, 'dict_size': 16777216}]
    assert lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters) is not None


@pytest.mark.unit
def test_read_archive_properties():
    buf = io.BytesIO()
    inp = binascii.unhexlify('0207012300')
    buf.write(inp)
    buf.seek(0, 0)
    ap = py7zr.archiveinfo.ArchiveProperties.retrieve(buf)
    assert ap.property_data[0] == (0x23, )  # FIXME: what it should be?


@pytest.mark.unit
@pytest.mark.parametrize("booleans, all_defined, expected",
                         [([True, False, True, True, False, True, False, False, True], False, b'\xb4\x80'),
                          ([True, False, True, True, False, True, False, False, True], True, b'\x00\xb4\x80')])
def test_write_booleans(booleans, all_defined, expected):
    buffer = io.BytesIO()
    py7zr.io.write_boolean(buffer, booleans, all_defined=all_defined)
    actual = buffer.getvalue()
    assert actual == expected


@pytest.mark.unit
@pytest.mark.parametrize("testinput, expected",
                         [(1, b'\x01'), (127, b'\x7f'), (128, b'\x80\x80'), (65535, b'\xc0\xff\xff'),
                          (0xffff7f, b'\xe0\x7f\xff\xff'), (0xffffffff, b'\xf0\xff\xff\xff\xff'),
                          (0x7f1234567f, b'\xf8\x7f\x56\x34\x12\x7f'),
                          (0x1234567890abcd, b'\xfe\xcd\xab\x90\x78\x56\x34\x12'),
                          (0xcf1234567890abcd, b'\xff\xcd\xab\x90\x78\x56\x34\x12\xcf')])
def test_write_uint64(testinput, expected):
    buf = io.BytesIO()
    py7zr.io.write_uint64(buf, testinput)
    actual = buf.getvalue()
    assert actual == expected


@pytest.mark.unit
@pytest.mark.parametrize("testinput, expected",
                         [(b'\x01', 1), (b'\x7f', 127), (b'\x80\x80', 128), (b'\xc0\xff\xff', 65535),
                          (b'\xe0\x7f\xff\xff', 0xffff7f), (b'\xf0\xff\xff\xff\xff', 0xffffffff),
                          (b'\xf8\x7f\x56\x34\x12\x7f', 0x7f1234567f),
                          (b'\xfe\xcd\xab\x90\x78\x56\x34\x12', 0x1234567890abcd),
                          (b'\xff\xcd\xab\x90\x78\x56\x34\x12\xcf', 0xcf1234567890abcd)])
def test_read_uint64(testinput, expected):
    buf = io.BytesIO(testinput)
    assert py7zr.io.read_uint64(buf) == expected


@pytest.mark.unit
def test_write_archive_properties():
    """
    test write function of ArchiveProperties class.
    Structure is as follows:
    BYTE Property.ARCHIVE_PROPERTIES (0x02)
       UINT64 PropertySize   (7 for test)
       BYTE PropertyData(PropertySize) b'0123456789abcd' for test
    BYTE Property.END (0x00)
    """
    archiveproperties = py7zr.archiveinfo.ArchiveProperties()
    archiveproperties.property_data = [binascii.unhexlify('0123456789abcd')]
    buf = io.BytesIO()
    archiveproperties.write(buf)
    assert buf.getvalue() == binascii.unhexlify('02070123456789abcd00')


@pytest.mark.unit
def test_write_packinfo():
    packinfo = py7zr.archiveinfo.PackInfo()
    packinfo.packpos = 0
    packinfo.packsizes = [48]
    packinfo.crcs = [py7zr.helpers.calculate_crc32(b'abcd')]
    buffer = io.BytesIO()
    packinfo.write(buffer)
    actual = buffer.getvalue()
    assert actual == b'\x06\x00\x01\t0\n\xf0\x11\xcd\x82\xed\x00'


@pytest.mark.unit
def test_startheader_calccrc():
    startheader = py7zr.archiveinfo.SignatureHeader()
    startheader.version = (0, 4)
    startheader.nextheaderofs = 1024
    startheader.nextheadersize = 32
    # set test data to buffer that start with Property.ENCODED_HEADER
    fp = open(os.path.join(testdata_path, 'test_5.7z'), 'rb')
    header_buf = io.BytesIO(b'\x17\x060\x01\tp\x00\x07\x0b\x01\x00\x01#\x03\x01\x01\x05]\x00'
                            b'\x00\x10\x00\x0c\x80\x9d\n\x01\xe5\xa1\xb7b\x00\x00')
    header = py7zr.archiveinfo.Header.retrieve(fp, header_buf, start_pos=32)
    startheader.calccrc(header)
    assert startheader.startheadercrc == 3257288896
    assert startheader.nextheadercrc == 1372678730