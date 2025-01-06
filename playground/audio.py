import time
import whisper
import speech_recognition as sr

def main():
    r = sr.Recognizer()
    with sr.AudioFile("audio/MicPhoneRecordings/Song idea.wav") as source:
        audio = r.record(source)
    r.recognize_google(audio)
    r.recognize_google(audio, language="sk")

    for model_name in ['tiny', 'base', 'small', 'medium']:
        model = whisper.load_model(model_name)
        print("Model", model_name)
        start = time.time()
        audio = whisper.load_audio("audio/MicPhoneRecordings/Song idea.m4a")
        audio = whisper.pad_or_trim(audio)
        mel = whisper.log_mel_spectrogram(audio, n_mels=model.dims.n_mels).to(model.device)
        _, probs = model.detect_language(mel)
        for k, v in sorted(list(probs.items()), key=lambda x: x[1]):
            if v < 0.01:
                continue
            print(k, v)
        options = whisper.DecodingOptions(language="sk")
        result = whisper.decode(model, mel, options)
        print("Decoded", result.text)
        print("Decoded langauge", result.language)
        end = time.time()
        print("Elapsed", end - start)

if __name__ == "__main__":
    main()
