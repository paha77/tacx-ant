import asyncio
import os
import threading

try:
  from dbus_next import BusType, Variant
  from dbus_next.aio import MessageBus
  from dbus_next.constants import PropertyAccess
  from dbus_next.service import ServiceInterface, dbus_property, method
except ImportError:
  BusType = None
  MessageBus = None
  Variant = None

  class PropertyAccess:
    READ = "read"

  class ServiceInterface:
    def __init__(self, name):
      self.name = name

    def emit_properties_changed(self, changed_properties, invalidated_properties):
      pass

  def method(*args, **kwargs):
    def decorate(function):
      return function
    return decorate

  def dbus_property(*args, **kwargs):
    def decorate(function):
      return property(function)
    return decorate


FTMS_SERVICE_UUID = "00001826-0000-1000-8000-00805f9b34fb"
FITNESS_MACHINE_FEATURE_UUID = "00002acc-0000-1000-8000-00805f9b34fb"
INDOOR_BIKE_DATA_UUID = "00002ad2-0000-1000-8000-00805f9b34fb"
SUPPORTED_RESISTANCE_LEVEL_RANGE_UUID = "00002ad6-0000-1000-8000-00805f9b34fb"
FITNESS_MACHINE_CONTROL_POINT_UUID = "00002ad9-0000-1000-8000-00805f9b34fb"
FITNESS_MACHINE_STATUS_UUID = "00002ada-0000-1000-8000-00805f9b34fb"
HEART_RATE_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HEART_RATE_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

FTMS_RESPONSE_CODE = 0x80
FTMS_SUCCESS = 0x01
FTMS_OPCODE_NOT_SUPPORTED = 0x02
FTMS_INVALID_PARAMETER = 0x03
FTMS_CONTROL_NOT_PERMITTED = 0x05
FTMS_REQUEST_CONTROL = 0x00
FTMS_RESET = 0x01
FTMS_SET_TARGET_RESISTANCE_LEVEL = 0x04
FTMS_SET_TARGET_POWER = 0x05
FTMS_START_OR_RESUME = 0x07
FTMS_STOP_OR_PAUSE = 0x08


def env_bool(name, default=False):
  value = os.environ.get(name)
  if value is None:
    return default
  return value.lower() in ("1", "true", "yes", "on")


def env_int(name, default):
  return int(os.environ.get(name, str(default)), 0)


MIN_RESISTANCE_LEVEL = env_int("ANTIFIER_BLUETOOTH_MIN_RESISTANCE", 0)
MAX_RESISTANCE_LEVEL = env_int("ANTIFIER_BLUETOOTH_MAX_RESISTANCE", 100)
RESISTANCE_INCREMENT = env_int("ANTIFIER_BLUETOOTH_RESISTANCE_INCREMENT", 1)


def clamp(value, low, high):
  return max(low, min(high, int(value)))


def indoor_bike_data_value(state):
  # FTMS Indoor Bike Data: instantaneous speed, cadence, resistance, power, and heart rate.
  flags = (1 << 2) | (1 << 5) | (1 << 6) | (1 << 9)
  instantaneous_speed = 0
  cadence_half_rpm = clamp(state.cadence, 0, 253) * 2
  resistance_level = clamp(getattr(state, "resistance", 0), -32768, 32767)
  power = clamp(state.power, -32768, 32767)
  heart_rate = clamp(state.heart_rate, 0, 255)
  return bytes([
    flags & 0xff,
    (flags >> 8) & 0xff,
    instantaneous_speed & 0xff,
    (instantaneous_speed >> 8) & 0xff,
    cadence_half_rpm & 0xff,
    (cadence_half_rpm >> 8) & 0xff,
    resistance_level & 0xff,
    (resistance_level >> 8) & 0xff,
    power & 0xff,
    (power >> 8) & 0xff,
    heart_rate,
  ])


def heart_rate_measurement_value(state):
  heart_rate = clamp(state.heart_rate, 0, 255)
  return bytes([0x00, heart_rate])


def int16_bytes(value):
  value = clamp(value, -32768, 32767)
  if value < 0:
    value += 65536
  return bytes([value & 0xff, (value >> 8) & 0xff])


def uint16_bytes(value):
  value = clamp(value, 0, 65535)
  return bytes([value & 0xff, (value >> 8) & 0xff])


def uint32_bytes(value):
  value = clamp(value, 0, 0xffffffff)
  return bytes([
    value & 0xff,
    (value >> 8) & 0xff,
    (value >> 16) & 0xff,
    (value >> 24) & 0xff,
  ])


def fitness_machine_feature_value():
  machine_features = (1 << 1) | (1 << 7) | (1 << 10) | (1 << 14)
  target_setting_features = (1 << 2) | (1 << 3)
  return uint32_bytes(machine_features) + uint32_bytes(target_setting_features)


def supported_resistance_level_range_value():
  return (
    int16_bytes(MIN_RESISTANCE_LEVEL * 10) +
    int16_bytes(MAX_RESISTANCE_LEVEL * 10) +
    uint16_bytes(max(1, RESISTANCE_INCREMENT) * 10)
  )


class BluetoothUnavailableError(RuntimeError):
  pass


class BluetoothBroadcaster:
  def __init__(self, name=None, adapter_path=None, debug=False):
    self.name = name or os.environ.get("ANTIFIER_BLUETOOTH_NAME", "Antifier")
    self.adapter_path = adapter_path or os.environ.get("ANTIFIER_BLUETOOTH_ADAPTER", "/org/bluez/hci0")
    self.debug = debug
    self.loop = None
    self.thread = None
    self.ready = threading.Event()
    self.stopped = threading.Event()
    self.error = None
    self.server = None

  def start(self):
    self.thread = threading.Thread(target=self._run_loop, name="antifier-ble", daemon=True)
    self.thread.start()
    self.ready.wait(timeout=15)
    if self.error:
      raise self.error
    if not self.ready.is_set():
      raise BluetoothUnavailableError("Timed out while registering Bluetooth GATT services")

  def broadcast(self, event_count, state, fec_page, hr_page):
    if not self.loop or self.error:
      return
    self.loop.call_soon_threadsafe(self.server.notify, state)

  def stop(self):
    if self.loop and self.server:
      future = asyncio.run_coroutine_threadsafe(self.server.stop(), self.loop)
      try:
        future.result(timeout=5)
      except Exception as exc:
        if self.debug:
          print("Bluetooth shutdown error: %s" % exc)
      self.loop.call_soon_threadsafe(self.loop.stop)
    if self.thread:
      self.thread.join(timeout=5)
    self.stopped.set()

  def _run_loop(self):
    self.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self.loop)
    self.server = BlueZServer(self.name, self.adapter_path, self.debug)
    try:
      self.loop.run_until_complete(self.server.start())
      self.ready.set()
      self.loop.run_forever()
    except Exception as exc:
      self.error = BluetoothUnavailableError(str(exc))
      self.ready.set()
    finally:
      try:
        self.loop.run_until_complete(self.server.stop())
      except Exception:
        pass
      self.loop.close()


class BlueZServer:
  def __init__(self, name, adapter_path, debug=False):
    self.name = name
    self.adapter_path = adapter_path
    self.debug = debug
    self.bus = None
    self.app_path = "/com/antifier"
    self.adv_path = "/com/antifier/advertisement0"
    self.gatt_manager = None
    self.ad_manager = None
    self.advertisement_registered = False
    self.application_registered = False
    self.current_state = EmptyState()
    self.control_acquired = False
    self.indoor_bike_characteristic = None
    self.control_point_characteristic = None
    self.status_characteristic = None
    self.heart_rate_characteristic = None

  async def start(self):
    if MessageBus is None:
      raise BluetoothUnavailableError(
        "Bluetooth mode requires dbus-next. Install it with: python3 -m pip install dbus-next"
      )

    self.bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    self._export_gatt_application()
    self._export_advertisement()

    adapter = await self._adapter_proxy()
    properties = adapter.get_interface("org.freedesktop.DBus.Properties")
    await properties.call_set("org.bluez.Adapter1", "Powered", Variant("b", True))

    self.gatt_manager = adapter.get_interface("org.bluez.GattManager1")
    self.ad_manager = adapter.get_interface("org.bluez.LEAdvertisingManager1")
    await self.gatt_manager.call_register_application(self.app_path, {})
    self.application_registered = True
    await self.ad_manager.call_register_advertisement(self.adv_path, {})
    self.advertisement_registered = True

  async def stop(self):
    if not self.bus:
      return
    if self.ad_manager and self.advertisement_registered:
      try:
        await self.ad_manager.call_unregister_advertisement(self.adv_path)
      except Exception:
        pass
      self.advertisement_registered = False
    if self.gatt_manager and self.application_registered:
      try:
        await self.gatt_manager.call_unregister_application(self.app_path)
      except Exception:
        pass
      self.application_registered = False
    try:
      self.bus.disconnect()
    except Exception:
      pass

  def notify(self, state):
    self.current_state = state
    if self.indoor_bike_characteristic:
      self.indoor_bike_characteristic.set_value(indoor_bike_data_value(state))
    if self.heart_rate_characteristic:
      self.heart_rate_characteristic.set_value(heart_rate_measurement_value(state))

  def handle_control_point_write(self, value):
    request = bytes(value)
    if not request:
      return self.control_point_response(0x00, FTMS_INVALID_PARAMETER)

    opcode = request[0]
    result = FTMS_SUCCESS
    if opcode == FTMS_REQUEST_CONTROL:
      self.control_acquired = True
    elif opcode == FTMS_RESET:
      if not self.control_acquired:
        result = FTMS_CONTROL_NOT_PERMITTED
      else:
        self.current_state.power = 150
        self.current_state.cadence = 90
        self.current_state.heart_rate = 120
        self.current_state.resistance = 0
    elif opcode == FTMS_SET_TARGET_RESISTANCE_LEVEL:
      if not self.control_acquired:
        result = FTMS_CONTROL_NOT_PERMITTED
      elif len(request) < 3:
        result = FTMS_INVALID_PARAMETER
      else:
        resistance_tenths = int.from_bytes(request[1:3], byteorder="little", signed=True)
        resistance = int(round(resistance_tenths / 10.0))
        self.current_state.resistance = clamp(
          resistance,
          MIN_RESISTANCE_LEVEL,
          MAX_RESISTANCE_LEVEL,
        )
    elif opcode == FTMS_SET_TARGET_POWER:
      if not self.control_acquired:
        result = FTMS_CONTROL_NOT_PERMITTED
      elif len(request) < 3:
        result = FTMS_INVALID_PARAMETER
      else:
        self.current_state.power = clamp(
          int.from_bytes(request[1:3], byteorder="little", signed=True),
          0,
          4093,
        )
    elif opcode in (FTMS_START_OR_RESUME, FTMS_STOP_OR_PAUSE):
      if not self.control_acquired:
        result = FTMS_CONTROL_NOT_PERMITTED
    else:
      result = FTMS_OPCODE_NOT_SUPPORTED

    if self.debug:
      print("FTMS control point write %s -> %s" % (request.hex(), result))
    return self.control_point_response(opcode, result)

  def control_point_response(self, opcode, result):
    response = bytes([FTMS_RESPONSE_CODE, opcode, result])
    if self.control_point_characteristic:
      self.control_point_characteristic.set_value(response)
    return response

  async def _adapter_proxy(self):
    introspection = await self.bus.introspect("org.bluez", self.adapter_path)
    return self.bus.get_proxy_object("org.bluez", self.adapter_path, introspection)

  def _export_gatt_application(self):
    objects = {}
    object_manager = ObjectManagerInterface(objects)
    self.bus.export(self.app_path, object_manager)

    ftms_service = GattServiceInterface(0, FTMS_SERVICE_UUID, True)
    ftms_path = self.app_path + "/service0"
    self.bus.export(ftms_path, ftms_service)
    objects[ftms_path] = [ftms_service]

    feature_characteristic = GattCharacteristicInterface(
      ftms_path,
      0,
      FITNESS_MACHINE_FEATURE_UUID,
      ["read"],
      fitness_machine_feature_value(),
    )
    feature_path = ftms_path + "/char0"
    self.bus.export(feature_path, feature_characteristic)
    objects[feature_path] = [feature_characteristic]

    self.indoor_bike_characteristic = GattCharacteristicInterface(
      ftms_path,
      1,
      INDOOR_BIKE_DATA_UUID,
      ["notify", "read"],
      indoor_bike_data_value(EmptyState()),
    )
    indoor_bike_path = ftms_path + "/char1"
    self.bus.export(indoor_bike_path, self.indoor_bike_characteristic)
    objects[indoor_bike_path] = [self.indoor_bike_characteristic]

    resistance_range_characteristic = GattCharacteristicInterface(
      ftms_path,
      2,
      SUPPORTED_RESISTANCE_LEVEL_RANGE_UUID,
      ["read"],
      supported_resistance_level_range_value(),
    )
    resistance_range_path = ftms_path + "/char2"
    self.bus.export(resistance_range_path, resistance_range_characteristic)
    objects[resistance_range_path] = [resistance_range_characteristic]

    self.control_point_characteristic = GattCharacteristicInterface(
      ftms_path,
      3,
      FITNESS_MACHINE_CONTROL_POINT_UUID,
      ["write", "indicate"],
      bytes([FTMS_RESPONSE_CODE, 0x00, FTMS_SUCCESS]),
      write_handler=self.handle_control_point_write,
    )
    control_point_path = ftms_path + "/char3"
    self.bus.export(control_point_path, self.control_point_characteristic)
    objects[control_point_path] = [self.control_point_characteristic]

    self.status_characteristic = GattCharacteristicInterface(
      ftms_path,
      4,
      FITNESS_MACHINE_STATUS_UUID,
      ["notify", "read"],
      bytes([0x00]),
    )
    status_path = ftms_path + "/char4"
    self.bus.export(status_path, self.status_characteristic)
    objects[status_path] = [self.status_characteristic]

    hr_service = GattServiceInterface(1, HEART_RATE_SERVICE_UUID, True)
    hr_path = self.app_path + "/service1"
    self.bus.export(hr_path, hr_service)
    objects[hr_path] = [hr_service]

    self.heart_rate_characteristic = GattCharacteristicInterface(
      hr_path,
      0,
      HEART_RATE_MEASUREMENT_UUID,
      ["notify", "read"],
      heart_rate_measurement_value(EmptyState()),
    )
    hr_char_path = hr_path + "/char0"
    self.bus.export(hr_char_path, self.heart_rate_characteristic)
    objects[hr_char_path] = [self.heart_rate_characteristic]

  def _export_advertisement(self):
    advertisement = AdvertisementInterface(
      self.name,
      [FTMS_SERVICE_UUID, HEART_RATE_SERVICE_UUID],
    )
    self.bus.export(self.adv_path, advertisement)

class EmptyState:
  power = 150
  cadence = 90
  heart_rate = 120
  resistance = 0


class ObjectManagerInterface(ServiceInterface):
  def __init__(self, objects):
    super().__init__("org.freedesktop.DBus.ObjectManager")
    self.objects = objects

  @method()
  def GetManagedObjects(self) -> "a{oa{sa{sv}}}":
    managed = {}
    for path, interfaces in self.objects.items():
      managed[path] = {}
      for interface in interfaces:
        managed[path][interface.name] = interface.get_properties()
    return managed


class GattServiceInterface(ServiceInterface):
  def __init__(self, index, uuid, primary):
    super().__init__("org.bluez.GattService1")
    self.path = "/com/antifier/service%d" % index
    self.uuid = uuid
    self.primary = primary

  def get_properties(self):
    return {
      "UUID": Variant("s", self.uuid),
      "Primary": Variant("b", self.primary),
      "Includes": Variant("ao", []),
    }

  @dbus_property(access=PropertyAccess.READ)
  def UUID(self) -> "s":
    return self.uuid

  @dbus_property(access=PropertyAccess.READ)
  def Primary(self) -> "b":
    return self.primary

  @dbus_property(access=PropertyAccess.READ)
  def Includes(self) -> "ao":
    return []


class GattCharacteristicInterface(ServiceInterface):
  def __init__(self, service_path, index, uuid, flags, initial_value, write_handler=None):
    super().__init__("org.bluez.GattCharacteristic1")
    self.service_path = service_path
    self.path = "%s/char%d" % (service_path, index)
    self.uuid = uuid
    self.flags = flags
    self.value = initial_value
    self.write_handler = write_handler
    self.notifying = False

  def get_properties(self):
    return {
      "UUID": Variant("s", self.uuid),
      "Service": Variant("o", self.service_path),
      "Flags": Variant("as", self.flags),
      "Notifying": Variant("b", self.notifying),
      "Value": Variant("ay", self.value),
    }

  def set_value(self, value):
    self.value = bytes(value)
    if self.notifying:
      self.emit_properties_changed({"Value": self.value}, [])

  @method()
  def ReadValue(self, options: "a{sv}") -> "ay":
    return self.value

  @method()
  def WriteValue(self, value: "ay", options: "a{sv}"):
    if self.write_handler:
      response = self.write_handler(value)
      if response is not None:
        self.value = bytes(response)
    else:
      self.value = bytes(value)

  @method()
  def StartNotify(self):
    self.notifying = True
    self.emit_properties_changed({"Notifying": self.notifying}, [])

  @method()
  def StopNotify(self):
    self.notifying = False
    self.emit_properties_changed({"Notifying": self.notifying}, [])

  @dbus_property(access=PropertyAccess.READ)
  def UUID(self) -> "s":
    return self.uuid

  @dbus_property(access=PropertyAccess.READ)
  def Service(self) -> "o":
    return self.service_path

  @dbus_property(access=PropertyAccess.READ)
  def Flags(self) -> "as":
    return self.flags

  @dbus_property(access=PropertyAccess.READ)
  def Notifying(self) -> "b":
    return self.notifying

  @dbus_property(access=PropertyAccess.READ)
  def Value(self) -> "ay":
    return self.value


class AdvertisementInterface(ServiceInterface):
  def __init__(self, local_name, service_uuids):
    super().__init__("org.bluez.LEAdvertisement1")
    self.local_name = local_name
    self.service_uuids = service_uuids

  def get_properties(self):
    return {
      "Type": Variant("s", "peripheral"),
      "ServiceUUIDs": Variant("as", self.service_uuids),
      "LocalName": Variant("s", self.local_name),
      "Includes": Variant("as", ["tx-power"]),
    }

  @method()
  def Release(self):
    pass

  @dbus_property(access=PropertyAccess.READ)
  def Type(self) -> "s":
    return "peripheral"

  @dbus_property(access=PropertyAccess.READ)
  def ServiceUUIDs(self) -> "as":
    return self.service_uuids

  @dbus_property(access=PropertyAccess.READ)
  def LocalName(self) -> "s":
    return self.local_name

  @dbus_property(access=PropertyAccess.READ)
  def Includes(self) -> "as":
    return ["tx-power"]
