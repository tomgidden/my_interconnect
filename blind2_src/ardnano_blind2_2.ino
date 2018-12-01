
//  Arduino Nano, ATmega328P (Old Bootloader), CH340G (or similar)

#include "config.h"

const int MOT_RPWM = 11;
const int MOT_LPWM = 10;
const int MOT_R_EN = 9;
const int MOT_L_EN = 8;
const int MOT_VCC  = 7;
const int MOT_GND  = 6;

#define ROT_PIN_A 3
#define ROT_PIN_B 2
#define ROT_PIN_REG PIND
#define ROT_PIN_SHIFT 2

volatile int pos = 0;
volatile int opos = 0;

int8_t read_encoder()
{
    static int8_t enc_states[] = {0,-1,1,0,1,0,0,-1,-1,0,0,1,0,1,-1,0};
    static uint8_t state = 0;
    state <<= 2;
    state |= ( (ROT_PIN_REG >> ROT_PIN_SHIFT) & 0x03 );
    return ( enc_states[(state & 0x0f)] );
}

void process_encoder()
{
    int8_t delta = read_encoder();
    if (delta) {
        opos = pos;
        pos += delta;
    }
}

void setup()
{
    pinMode(MOT_GND, OUTPUT);
    pinMode(MOT_VCC, OUTPUT);
    pinMode(MOT_L_EN, OUTPUT);
    pinMode(MOT_R_EN, OUTPUT);
    pinMode(MOT_LPWM, OUTPUT);
    pinMode(MOT_RPWM, OUTPUT);

    digitalWrite(MOT_GND, false);
    digitalWrite(MOT_VCC, true);
    digitalWrite(MOT_L_EN, true);
    digitalWrite(MOT_R_EN, true);

    pinMode(ROT_PIN_A, INPUT_PULLUP);
    pinMode(ROT_PIN_B, INPUT_PULLUP);

    int iA = digitalPinToInterrupt(ROT_PIN_A);
    int iB = digitalPinToInterrupt(ROT_PIN_B);

    Serial.begin(115200);

    attachInterrupt(iA, process_encoder, CHANGE);
    attachInterrupt(iB, process_encoder, CHANGE);
}

static int npos;


static int motorSpeed = 0;
static unsigned long motorStopBy = 0;

static void motor_set_speed(int _speed, int _target)
{
    motorStopBy = millis() + (long)_target;
    motorSpeed = _speed;

    digitalWrite(MOT_L_EN, true);
    digitalWrite(MOT_R_EN, true);
    if (0 > _speed) {
        analogWrite(MOT_LPWM, -_speed);
        analogWrite(MOT_RPWM, 0);
    } else {
        analogWrite(MOT_RPWM, _speed);
        analogWrite(MOT_LPWM, 0);
    }
}

static void motor_active_stop()
{
    motorSpeed = 0;
    motorStopBy = 0;
    digitalWrite(MOT_L_EN, true);
    digitalWrite(MOT_R_EN, true);
    analogWrite(MOT_LPWM, 0);
    analogWrite(MOT_RPWM, 0);
}

static void motor_resting_stop()
{
    motorSpeed = 0;
    motorStopBy = 0;
    digitalWrite(MOT_L_EN, false);
    digitalWrite(MOT_R_EN, false);
    analogWrite(MOT_LPWM, 0);
    analogWrite(MOT_RPWM, 0);
}

static void handle_serial()
{
    static int inCmd;
    static int inSpeed, inParam;

    if (Serial.available() > 0) {
        inCmd = Serial.read();

        switch (inCmd) {
        case 'Z':
            opos = pos = 0;
            Serial.println("R0");
            break;

        case 'S': {
            inSpeed = Serial.parseInt();
            inParam = Serial.parseInt();

            if (inSpeed > 255 or inSpeed < -255) {
                // Fault. Stop.
                motor_active_stop();
            }
            else if (0 == inSpeed) {
                motor_active_stop();
            }
            else {
                motor_set_speed(inSpeed, inParam);
            }
        }
            break;
        }
    }
}

static void handle_termination()
{
    if (!motorStopBy)
        return;

    if (0 != motorSpeed)
        motor_active_stop();
    else
        motor_resting_stop();
}

void loop()
{
    cli();
    if (opos != pos) {
        npos = pos;
        opos = npos;
        npos = true;
    }
    sei();

    if (npos == true) {
        Serial.print("R");
        Serial.println(pos);
        npos = false;
    }

    handle_serial();

    if (millis() > motorStopBy)
      handle_termination();

    delay(50);
}
