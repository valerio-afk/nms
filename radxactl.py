from RPi import GPIO
from os import environ
import time
import requests
import threading
import sys
import atexit
import socket

atexit.register(GPIO.cleanup)

FAN_PULSE_COUNT = 0

TEMP_RANGE={
    'cpu': (35,80),
    'hdd': (20,45)
}

SATA_12_ENABLE = int(environ.get('SATA_12_ENABLE',"25"))
SATA_34_ENABLE = int(environ.get('SATA_34_ENABLE',"26"))
FAN_PWM = int(environ.get('FAN_PWM',"13"))
FAN_SENSING = int(environ.get('FAN_SENSING',"23"))



GPIO.setmode(GPIO.BCM)
GPIO.setup(SATA_12_ENABLE, GPIO.OUT)
GPIO.setup(SATA_34_ENABLE, GPIO.OUT)

GPIO.setup(FAN_PWM, GPIO.OUT)
GPIO.setup(FAN_SENSING, GPIO.IN,pull_up_down=GPIO.PUD_UP)

print(f"SATA Port 1&2 Enable GPIO: {SATA_12_ENABLE}",file=sys.stderr)
print(f"SATA Port 3&4 Enable GPIO: {SATA_34_ENABLE}",file=sys.stderr)
print(f"Fan PWM GPIO: {FAN_PWM}",file=sys.stderr)
print(f"Fan Sensing GPIO: {FAN_SENSING}",file=sys.stderr)


PWM_MNGT = GPIO.PWM(FAN_PWM, 1000)
PWM_MNGT.start(100)

def notify_ready():
    sock = environ.get("NOTIFY_SOCKET")
    if sock:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s.connect(sock)
        s.sendall(b"READY=1")
        s.close()

def pwm_sensing_thread():
    while True:
        count = 0
        time.sleep(1)
        rpm = (count / 2) * 60
        with open("/run/gpio_fan","w") as f:
            f.write(f"GPIO Fan: {rpm} RPM\n")


def pwm_pulse_count(_):
    global FAN_PULSE_COUNT
    FAN_PULSE_COUNT += 1


def temp_monitor():
    global TEMP_RANGE, PWM_MNGT
    url = "https://localhost:8081/v1/system/sensors"

    while True:
        duty_cycle = 100
        response_ok = False
        try:
            response = requests.get(url,timeout=5)
            response_ok = True
        except:
            pass

        if (response_ok) and (response.status_code == 200):
            data = {}
            try:
                data = response.json()
            except:
                pass

            temperatures = {k: -1 for k in TEMP_RANGE}

            for sensor in data:
                if (sensor.get("type") in ["cpu", "hdd"]):
                    temperatures[sensor.get("type")] = max(temperatures[sensor.get("type")], sensor.get("temperature",-1))

            new_duty_cycle = -1

            for k, (temp_min, temp_max) in TEMP_RANGE.items():
                proposed_dt = -1
                if ((t := temperatures[k]) > -1):
                    if (t < temp_min):
                        proposed_dt = 0
                    elif (t > temp_max):
                        proposed_dt = 100
                    else:
                        proposed_dt = int((t - temp_min) / (temp_max - temp_min) * 100)

                new_duty_cycle = max(new_duty_cycle, proposed_dt)

            if (new_duty_cycle != -1):
                duty_cycle = new_duty_cycle

        PWM_MNGT.ChangeDutyCycle(duty_cycle)
        time.sleep(10)

GPIO.add_event_detect(FAN_SENSING, GPIO.FALLING, callback=pwm_pulse_count)

GPIO.output(SATA_12_ENABLE, GPIO.HIGH)
GPIO.output(SATA_34_ENABLE, GPIO.HIGH)

t1 = threading.Thread(target=pwm_sensing_thread)
t1.start()

t2 = threading.Thread(target=temp_monitor)
t2.start()

time.sleep(2)

notify_ready()