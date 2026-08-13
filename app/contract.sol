// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/// @notice Append-only log of PKG fragment disclosures. Holds no plaintext
/// and no keys -- only enough to let anyone verify what was published, by
/// whom, and under what policy, and to retrieve the encrypted blob from
/// off-chain storage via its content-addressed CID.
contract PKGRegistry {
    struct Share {
        address owner;
        string cid;
        bytes32 contentHash;
        bytes32 policyHash;
        uint256 version;
        uint256 timestamp;
    }

    Share[] public shares;

    event SharePublished(
        uint256 indexed id,
        address indexed owner,
        string cid,
        bytes32 contentHash,
        bytes32 policyHash,
        uint256 version
    );

    function publishShare(
        string calldata cid,
        bytes32 contentHash,
        bytes32 policyHash,
        uint256 version
    ) external returns (uint256 id) {
        shares.push(Share(msg.sender, cid, contentHash, policyHash, version, block.timestamp));
        id = shares.length - 1;
        emit SharePublished(id, msg.sender, cid, contentHash, policyHash, version);
    }

    function shareCount() external view returns (uint256) {
        return shares.length;
    }
}
