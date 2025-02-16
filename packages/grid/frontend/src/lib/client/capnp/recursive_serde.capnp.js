'use strict';

/**
 * This file has been automatically generated by the [capnpc-ts utility](https://github.com/jdiaz5513/capnp-ts).
 */
import * as capnp from 'capnp-ts';
import * as capnp_ts_1 from 'capnp-ts';
export const _capnpFileId = BigInt('0xd7dd27f3820d22ee');
export class RecursiveSerde extends capnp_ts_1.Struct {
  /**
   * @param {capnp.Orphan<capnp.Pointer>} value
   */
  adoptFieldsName(value) {
    capnp_ts_1.Struct.adopt(value, capnp_ts_1.Struct.getPointer(0, this));
  }
  disownFieldsName() {
    return capnp_ts_1.Struct.disown(this.getFieldsName());
  }
  getFieldsName() {
    return capnp_ts_1.Struct.getList(0, capnp.TextList, this);
  }
  hasFieldsName() {
    return !capnp_ts_1.Struct.isNull(capnp_ts_1.Struct.getPointer(0, this));
  }
  /**
   * @param {number} length
   */
  initFieldsName(length) {
    return capnp_ts_1.Struct.initList(0, capnp.TextList, length, this);
  }
  /**
   * @param {capnp.Pointer} value
   */
  setFieldsName(value) {
    capnp_ts_1.Struct.copyFrom(value, capnp_ts_1.Struct.getPointer(0, this));
  }
  /**
   * @param {capnp.Orphan<capnp.Pointer>} value
   */
  adoptFieldsData(value) {
    capnp_ts_1.Struct.adopt(value, capnp_ts_1.Struct.getPointer(1, this));
  }
  disownFieldsData() {
    return capnp_ts_1.Struct.disown(this.getFieldsData());
  }
  getFieldsData() {
    return capnp_ts_1.Struct.getList(1, RecursiveSerde._FieldsData, this);
  }
  hasFieldsData() {
    return !capnp_ts_1.Struct.isNull(capnp_ts_1.Struct.getPointer(1, this));
  }
  /**
   * @param {number} length
   */
  initFieldsData(length) {
    return capnp_ts_1.Struct.initList(1, RecursiveSerde._FieldsData, length, this);
  }
  /**
   * @param {capnp.Pointer} value
   */
  setFieldsData(value) {
    capnp_ts_1.Struct.copyFrom(value, capnp_ts_1.Struct.getPointer(1, this));
  }
  getFullyQualifiedName() {
    return capnp_ts_1.Struct.getText(2, this);
  }
  /**
   * @param {string} value
   */
  setFullyQualifiedName(value) {
    capnp_ts_1.Struct.setText(2, value, this);
  }
  /**
   * @param {capnp.Orphan<capnp.Pointer>} value
   */
  adoptNonrecursiveBlob(value) {
    capnp_ts_1.Struct.adopt(value, capnp_ts_1.Struct.getPointer(3, this));
  }
  disownNonrecursiveBlob() {
    return capnp_ts_1.Struct.disown(this.getNonrecursiveBlob());
  }
  getNonrecursiveBlob() {
    return capnp_ts_1.Struct.getList(3, capnp.DataList, this);
  }
  hasNonrecursiveBlob() {
    return !capnp_ts_1.Struct.isNull(capnp_ts_1.Struct.getPointer(3, this));
  }
  /**
   * @param {number} length
   */
  initNonrecursiveBlob(length) {
    return capnp_ts_1.Struct.initList(3, capnp.DataList, length, this);
  }
  /**
   * @param {capnp.Pointer} value
   */
  setNonrecursiveBlob(value) {
    capnp_ts_1.Struct.copyFrom(value, capnp_ts_1.Struct.getPointer(3, this));
  }
  toString() {
    return 'RecursiveSerde_' + super.toString();
  }
}

RecursiveSerde._capnp = {
  displayName: 'RecursiveSerde',
  id: 'f8884f5048511037',
  size: new capnp_ts_1.ObjectSize(0, 4)
};
RecursiveSerde._FieldsData = capnp.PointerList(capnp.DataList);
