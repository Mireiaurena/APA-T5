import numpy as np
import struct as st
import matplotlib.pyplot as plt

fichero = 'komm.wav'
salida1 = 'sortida1.wav'
salida2 = 'sortida2.wav'
salida3 = 'sortida3.wav'
salida4 = 'sortida4.wav'
FicIzq = 'izq.wav'
FicDer = 'der.wav'


def estereo2mono(ficEste, ficMono, canal=2):
    with open(ficEste, 'rb') as f:
        riff, size, fformat = st.unpack('<4sI4s', f.read(12))
        if riff != b'RIFF' or fformat != b'WAVE':
            raise Exception("No es un archivo WAV válido.")

        fmt_chunk_found = False
        data_chunk_found = False

        while not fmt_chunk_found:
            chunk_id, chunk_size = st.unpack('<4sI', f.read(8))
            if chunk_id == b'fmt ':
                fmt_data = f.read(chunk_size)
                fmt_chunk_found = True
            else:
                f.seek(chunk_size, 1)

        audio_format, num_channels, sample_rate, byte_rate, block_align, bits_per_sample = st.unpack('<HHIIHH', fmt_data[:16])
        if num_channels != 2 or bits_per_sample != 16:
            raise Exception("Este programa solo soporta WAV estéreo PCM de 16 bits.")

        while not data_chunk_found:
            chunk_id, chunk_size = st.unpack('<4sI', f.read(8))
            if chunk_id == b'data':
                data_chunk_found = True
                data = f.read(chunk_size)
            else:
                f.seek(chunk_size, 1)

    num_samples = len(data) // 4  
    L = []
    R = []
    mono = []

    for i in range(0, len(data), 4):
        l, r = st.unpack('<hh', data[i:i+4])
        L.append(l)
        R.append(r)
        if canal == 0:
            m = l
        elif canal == 1:
            m = r
        elif canal == 2:
            m = (l + r) // 2
        elif canal == 3:
            m = (l - r) // 2
        else:
            raise ValueError("Canal inválido.")
        mono.append(m)

    muestras_mono = b''.join([st.pack('<h', m) for m in mono])
    subchunk2_size = len(muestras_mono)
    chunk_size = 36 + subchunk2_size

    header = st.pack('<4sI4s', b'RIFF', chunk_size, b'WAVE')
    fmt = st.pack('<4sIHHIIHH', b'fmt ', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    data_header = st.pack('<4sI', b'data', subchunk2_size)

    with open(ficMono, 'wb') as f:
        f.write(header)
        f.write(fmt)
        f.write(data_header)
        f.write(muestras_mono)


def mono2estereo(ficIzq, ficDer, ficEste):
    def leer_cabecera_y_datos(fic):
        with open(fic, 'rb') as f:
            riff, size, fformat = st.unpack('<4sI4s', f.read(12))
            if riff != b'RIFF' or fformat != b'WAVE':
                raise Exception(f'{fic} no tiene formato WAV válido.')

            while True:
                chunk_id, chunk_size = st.unpack('<4sI', f.read(8))
                if chunk_id == b'fmt ':
                    fmt_data = f.read(chunk_size)
                    break
                else:
                    f.seek(chunk_size, 1)

            audio_format, num_channels, sample_rate, byte_rate, block_align, bits_per_sample = st.unpack('<HHIIHH', fmt_data[:16])
            if num_channels != 1 or bits_per_sample != 16:
                raise Exception(f'{fic} no es un archivo mono PCM de 16 bits.')

            while True:
                chunk_id, chunk_size = st.unpack('<4sI', f.read(8))
                if chunk_id == b'data':
                    data = f.read(chunk_size)
                    break
                else:
                    f.seek(chunk_size, 1)

        return sample_rate, np.frombuffer(data, dtype='<i2')

    fs_L, L = leer_cabecera_y_datos(ficIzq)
    fs_R, R = leer_cabecera_y_datos(ficDer)

    if fs_L != fs_R:
        raise Exception("Las frecuencias de muestreo no coinciden.")
    if len(L) != len(R):
        raise Exception("Los tamaños de los datos no coinciden.")

    num_muestras = len(L)

    intercalado = np.empty((num_muestras * 2,), dtype='<i2')
    intercalado[0::2] = L
    intercalado[1::2] = R
    stereo_bytes = intercalado.tobytes()

    subchunk2_size = len(stereo_bytes)
    chunk_size = 36 + subchunk2_size

    with open(ficEste, 'wb') as f:
        f.write(st.pack('<4sI4s', b'RIFF', chunk_size, b'WAVE'))
        f.write(st.pack('<4sIHHIIHH', b'fmt ', 16, 1, 2, fs_L, fs_L * 4, 4, 16))
        f.write(st.pack('<4sI', b'data', subchunk2_size))
        f.write(stereo_bytes)


def codEstereo(ficEste, ficCod):
    with open(ficEste, 'rb') as f:
        header = f.read(44)
        fmt = '<4sI4s4sIHHIIHH4sI'
        campos = list(st.unpack(fmt, header))

        n_channels = campos[6]
        sample_rate = campos[7]
        bits_per_sample = campos[10]
        data_size = campos[12]

        if n_channels != 2 or bits_per_sample != 16:
            raise Exception("El archivo debe ser estéreo con muestras de 16 bits.")

        raw_data = f.read(data_size)
        samples = np.frombuffer(raw_data, dtype='<i2')

    L = samples[::2]
    R = samples[1::2]

    codificados = ((L.astype(np.uint32) & 0xFFFF) << 16) | (R.astype(np.uint32) & 0xFFFF)

    with open(ficCod, 'wb') as f:
        f.write(st.pack('<' + 'I' * len(codificados), *codificados))

    return sample_rate


def decEstereo(ficCod, ficEste, sample_rate=44100):
    with open(ficCod, 'rb') as f:
        data = f.read()
        codificados = np.frombuffer(data, dtype='<u4')

    L = ((codificados >> 16) & 0xFFFF).astype('<i2')
    R = (codificados & 0xFFFF).astype('<i2')

    interleaved = np.empty(len(L) * 2, dtype='<i2')
    interleaved[0::2] = L
    interleaved[1::2] = R

    data_bytes = interleaved.tobytes()
    subchunk2_size = len(data_bytes)
    chunk_size = 36 + subchunk2_size
    byte_rate = sample_rate * 2 * 2
    block_align = 2 * 2

    header = st.pack('<4sI4s', b'RIFF', chunk_size, b'WAVE')
    header += st.pack('<4sIHHIIHH', b'fmt ', 16, 1, 2, sample_rate, byte_rate, block_align, 16)
    header += st.pack('<4sI', b'data', subchunk2_size)

    with open(ficEste, 'wb') as f:
        f.write(header)
        f.write(data_bytes)


if __name__ == '__main__':
    fic_binario = 'audio_codificado.bin'
    
    try:
        estereo2mono(fichero, FicIzq, canal=0)
        estereo2mono(fichero, FicDer, canal=1)
        
        estereo2mono(fichero, salida3, canal=2)
        mono2estereo(FicIzq, FicDer, salida2)
        fs_original = codEstereo(fichero, fic_binario)
        decEstereo(fic_binario, salida1, sample_rate=fs_original)
        
        with open(fichero, 'rb') as f:
            f.seek(24)
            fs = st.unpack('<I', f.read(4))[0]

        with open(fichero, 'rb') as f:
            f.seek(44)
            muestras_est = np.frombuffer(f.read(), dtype='<i2').reshape(-1, 2)
        with open(salida3, 'rb') as f:
            f.seek(44)
            muestras_mono = np.frombuffer(f.read(), dtype='<i2')

        tiempo_30s = np.arange(len(muestras_mono)) / fs

        fig1, axs1 = plt.subplots(1, 2, figsize=(13, 4))
        fig1.canvas.manager.set_window_title('estereo2mono()')
        axs1[0].plot(tiempo_30s, muestras_est[:, 0], label='Izquierdo (L)', color='blue', alpha=0.7, linewidth=1)
        axs1[0].plot(tiempo_30s, muestras_est[:, 1], label='Derecho (R)', color='red', alpha=0.6, linewidth=1)
        axs1[0].set_title('Señal Estéreo')
        axs1[0].set_xlabel('Tiempo [s]')
        axs1[0].set_ylabel('Amplitud')
        axs1[0].legend(loc='upper left')

        axs1[1].plot(tiempo_30s, muestras_mono, color='magenta', linewidth=1)
        axs1[1].set_title('Señal Monofónica')
        axs1[1].set_xlabel('Tiempo [s]')
        axs1[1].set_ylabel('Amplitud')
        plt.tight_layout()

        with open(FicIzq, 'rb') as f:
            f.seek(44)
            datos_izq = np.frombuffer(f.read(), dtype='<i2')
        with open(FicDer, 'rb') as f:
            f.seek(44)
            datos_der = np.frombuffer(f.read(), dtype='<i2')
        with open(salida2, 'rb') as f:
            f.seek(44)
            datos_comb = np.frombuffer(f.read(), dtype='<i2').reshape(-1, 2)

        fig2, axs2 = plt.subplots(1, 3, figsize=(15, 4))
        fig2.canvas.manager.set_window_title('mono2estereo()')
        axs2[0].plot(tiempo_30s, datos_izq, color='blue', linewidth=1)
        axs2[0].set_title('Mono Izquierdo')
        axs2[0].set_xlabel('Tiempo [s]')
        axs2[0].set_ylabel('Amplitud')

        axs2[1].plot(tiempo_30s, datos_der, color='red', linewidth=1)
        axs2[1].set_title('Mono Derecho')
        axs2[1].set_xlabel('Tiempo [s]')

        axs2[2].plot(tiempo_30s, datos_comb[:, 0], color='blue', alpha=0.6, label='L', linewidth=1)
        axs2[2].plot(tiempo_30s, datos_comb[:, 1], color='red', alpha=0.6, label='R', linewidth=1)
        axs2[2].set_title('Señal Estéreo Combinada')
        axs2[2].set_xlabel('Tiempo [s]')
        axs2[2].legend(loc='upper left')
        plt.tight_layout()

        fig3, axs3 = plt.subplots(1, 2, figsize=(13, 4))
        fig3.canvas.manager.set_window_title('codEstereo()')
        axs3[0].plot(tiempo_30s, muestras_est[:, 0], color='blue', linewidth=1)
        axs3[0].set_title('Canal Izquierdo')
        axs3[0].set_xlabel('Tiempo [s]')
        axs3[0].set_ylabel('Amplitud')

        axs3[1].plot(tiempo_30s, muestras_est[:, 1], color='red', linewidth=1)
        axs3[1].set_title('Canal Derecho')
        axs3[1].set_xlabel('Tiempo [s]')
        plt.tight_layout()

        with open(salida1, 'rb') as f:
            f.seek(44)
            muestras_dec = np.frombuffer(f.read(), dtype='<i2').reshape(-1, 2)

        tiempo_10s = np.arange(len(muestras_dec)) / (fs * 2.75)

        fig4, axs4 = plt.subplots(1, 2, figsize=(13, 4))
        fig4.canvas.manager.set_window_title('decEstereo()')
        axs4[0].plot(tiempo_10s, muestras_dec[:, 0], color='blue', linewidth=1)
        axs4[0].set_title('Canal Izquierdo (Decodificado)')
        axs4[0].set_xlabel('Tiempo [s]')
        axs4[0].set_ylabel('Amplitud')
        axs4[0].set_xlim(-0.5, 11)

        axs4[1].plot(tiempo_10s, muestras_dec[:, 1], color='red', linewidth=1)
        axs4[1].set_title('Canal Derecho (Decodificado)')
        axs4[1].set_xlabel('Tiempo [s]')
        axs4[1].set_xlim(-0.5, 11)
        plt.tight_layout()

        plt.show()

    except Exception as e:
        print(f"\n[ERROR]: {e}")