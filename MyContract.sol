// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract NonWorkCertificate {
    struct Certificate {
        string name;
        string date;
        string declaration;
        bool exists;
    }

    mapping(address => Certificate) public certificates;

    event CertificateCreated(address indexed certificateHolder, string name, string date, string declaration);

    constructor(string memory _name, string memory _date, string memory _declaration) {
        certificates[msg.sender] = Certificate(_name, _date, _declaration, true);
    }

    function getCertificate(address _addr) public view returns (string memory, string memory, string memory, bool) {
        Certificate memory cert = certificates[_addr];
        return (cert.name, cert.date, cert.declaration, cert.exists);
    }

    function createCertificate(string memory _name, string memory _date, string memory _declaration) public {
        certificates[msg.sender] = Certificate(_name, _date, _declaration, true);
        emit CertificateCreated(msg.sender, _name, _date, _declaration);
    }
}
